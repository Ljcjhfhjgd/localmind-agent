"""
文件名: tools/xray/model.py
功能: 胸片诊断模型 - 加载 + 推理（加密支持）
"""
import io
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import transforms, models
from PIL import Image
import numpy as np
import yaml
from loguru import logger

# 模型加密 KEY
KEY = b'3fik6HnQrKMunEXhtTdslF1utDaDTU_DnVWD1R_qpBo='

# 疾病标签
LABELS_EN = [
    "Atelectasis", "Cardiomegaly", "Consolidation", "Edema", "Effusion",
    "Emphysema", "Fibrosis", "Hernia", "Infiltration", "Mass",
    "Nodule", "Pleural Thickening", "Pneumonia", "Pneumothorax",
    "Pneumoperitoneum", "Pneumomediastinum", "Subcutaneous Emphysema",
    "Tortuous Aorta", "Calcification of the Aorta", "No Finding"
]

LABELS_CN = [
    "肺不张", "心脏肥大", "实变", "肺水肿", "胸腔积液",
    "肺气肿", "纤维化", "疝", "浸润", "肿块",
    "结节", "胸膜增厚", "肺炎", "气胸", "气腹",
    "纵隔气肿", "皮下气肿", "主动脉迂曲", "主动脉钙化", "未见明显异常"
]


def _load_model_path_from_config() -> str:
    """从 config.yaml 读取模型路径"""
    config_path = Path(__file__).resolve().parent.parent.parent / "config.yaml"
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            xray_cfg = config.get('xray', {})
            path = xray_cfg.get('model_path', '')
            if path:
                return path
        except Exception as e:
            logger.warning(f"读取 config.yaml 失败: {e}")
    return "tools/xray/xray_models/best_classifier.pth"


def _load_checkpoint(model_path: str) -> dict:
    """加载模型权重，优先加密文件"""
    from cryptography.fernet import Fernet

    enc_path = Path(model_path).with_suffix('.enc')
    if enc_path.exists():
        logger.info("加载加密分类模型...")
        f = Fernet(KEY)
        decrypted = f.decrypt(enc_path.read_bytes())
        return torch.load(io.BytesIO(decrypted), map_location='cpu', weights_only=False)

    plain_path = Path(model_path)
    if plain_path.exists():
        logger.info("加载明文分类模型...")
        return torch.load(str(plain_path), map_location='cpu', weights_only=False)

    raise FileNotFoundError(f"模型文件不存在: {model_path}")


class ImageEncoder(nn.Module):
    """图像编码器（与预训练一致，带投影层）"""
    def __init__(self, embed_dim=512):
        super().__init__()
        self.backbone = models.resnet50(weights=None)
        self.backbone.fc = nn.Identity()
        self.proj = nn.Linear(2048, embed_dim)

    def forward(self, x):
        return F.normalize(self.proj(self.backbone(x)), dim=-1)


class Classifier(nn.Module):
    """分类器（与微调时一致：冻结编码器 + 分类头）"""
    def __init__(self, encoder, num_classes=20, embed_dim=512):
        super().__init__()
        self.encoder = encoder
        for param in self.encoder.parameters():
            param.requires_grad = False
        self.fc = nn.Linear(embed_dim, num_classes)

    def forward(self, x):
        with torch.no_grad():
            features = self.encoder(x)
        return self.fc(features)


class XRayModel:
    """胸片诊断模型"""

    def __init__(self, model_path: str = None):
        self.model = None
        self.transform = None
        self.device = None
        self.model_path = model_path or _load_model_path_from_config()
        self._loaded = False

    def load(self):
        """加载模型"""
        if self._loaded:
            return

        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        checkpoint = _load_checkpoint(self.model_path)

        encoder = ImageEncoder()
        self.model = Classifier(encoder, num_classes=20)

        state_dict = checkpoint.get('model_state_dict', checkpoint)
        if any(k.startswith('module.') for k in state_dict.keys()):
            state_dict = {k.replace('module.', ''): v for k, v in state_dict.items()}
        self.model.load_state_dict(state_dict, strict=True)
        self.model.to(self.device).eval()

        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])

        self._loaded = True
        logger.info(f"胸片模型已加载: {self.device}")

    def predict(self, image_bytes: bytes) -> dict:
        """预测"""
        self.load()

        img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        img_tensor = self.transform(img).unsqueeze(0).to(self.device)

        with torch.no_grad():
            probs = torch.sigmoid(self.model(img_tensor)).squeeze().cpu().numpy()

        ranked = sorted(enumerate(probs), key=lambda x: x[1], reverse=True)
        no_finding_prob = round(float(probs[19]) * 100, 1)
        is_no_finding_top1 = ranked[0][0] == 19

        top3 = []
        for idx, prob in ranked:
            if idx == 19:
                continue
            top3.append({
                "disease_cn": LABELS_CN[idx],
                "disease_en": LABELS_EN[idx],
                "probability": round(float(prob) * 100, 1)
            })
            if len(top3) == 3:
                break

        disease_probs = {}
        for i in range(19):
            disease_probs[LABELS_CN[i]] = float(probs[i]) * 100

        high_confidence = [(d, p) for d, p in disease_probs.items() if p > 80]
        suspicious = [(d, p) for d, p in disease_probs.items() if p > 50]
        max_disease_prob = max(disease_probs.values()) if disease_probs else 0
        total_disease_prob = sum(disease_probs.values())

        if no_finding_prob < 40:
            category = "异常"
            reason = f"模型不认为正常（No Finding: {no_finding_prob}%）"
        elif high_confidence:
            diseases = ", ".join([f"{d}({p}%)" for d, p in high_confidence])
            category = "异常"
            reason = f"高置信度发现: {diseases}"
        elif no_finding_prob > 70 and max_disease_prob < 30:
            category = "正常"
            reason = f"胸片干净，未见明确异常（No Finding: {no_finding_prob}%）"
        elif len(suspicious) >= 2:
            diseases = ", ".join([f"{d}({p}%)" for d, p in suspicious])
            category = "建议复查"
            reason = f"多个可疑发现（{len(suspicious)}个）: {diseases}"
        elif total_disease_prob > 80:
            category = "建议复查"
            reason = f"多个低置信度异常叠加（总风险: {round(total_disease_prob, 1)}%）"
        elif no_finding_prob > 60:
            category = "建议复查"
            reason = f"正常倾向但不够确定（No Finding: {no_finding_prob}%）"
        else:
            category = "建议复查"
            reason = "边界模糊，建议医生复核"

        return {
            "no_finding_prob": no_finding_prob,
            "is_no_finding_top1": is_no_finding_top1,
            "top3": top3,
            "category": category,
            "reason": reason
        }

    def predict_all(self, image_bytes: bytes) -> dict:
        """返回全部 20 类概率：No Finding + 19 种疾病按概率降序"""
        self.load()

        img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        img_tensor = self.transform(img).unsqueeze(0).to(self.device)

        with torch.no_grad():
            probs = torch.sigmoid(self.model(img_tensor)).squeeze().cpu().numpy()

        no_finding_prob = round(float(probs[19]) * 100, 1)

        diseases = []
        for i in range(19):
            diseases.append({
                "disease_cn": LABELS_CN[i],
                "disease_en": LABELS_EN[i],
                "probability": round(float(probs[i]) * 100, 1)
            })
        diseases.sort(key=lambda x: x["probability"], reverse=True)

        return {
            "no_finding_prob": no_finding_prob,
            "diseases": diseases
        }