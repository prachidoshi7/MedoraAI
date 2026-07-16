"""
MedoraAI — SQLAlchemy ORM Models
Tables: users, scans, results, reports
"""

from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


class User(Base):
    """Authentication table. Seeded with demo user on first run."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    scans = relationship("Scan", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"


class Scan(Base):
    """Uploaded medical image records."""
    __tablename__ = "scans"

    id = Column(String(36), primary_key=True)  # UUID v4 string
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String(255), nullable=False)  # Original filename
    scan_type = Column(String(20), nullable=False, default="chest_xray")  # "chest_xray" or "brain_mri"
    modality = Column(String(50), default="X-ray")  # "X-ray", "MRI", "CT", "Unknown"
    file_path = Column(String(500), nullable=False)  # /data/uploads/{id}.png
    heatmap_path = Column(String(500))  # /data/heatmaps/{id}.png (NULL until analyzed)
    thumbnail_path = Column(String(500))  # /data/thumbnails/{id}.png
    file_size_bytes = Column(Integer)
    status = Column(String(20), default="uploaded")  # uploaded, analyzing, analyzed, failed
    uploaded_at = Column(DateTime, server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="scans")
    result = relationship("Result", back_populates="scan", uselist=False, cascade="all, delete-orphan")
    report = relationship("Report", back_populates="scan", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Scan(id='{self.id[:8]}', type='{self.scan_type}', status='{self.status}')>"


class Result(Base):
    """AI inference results. One-to-one with analyzed scans."""
    __tablename__ = "results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scan_id = Column(String(36), ForeignKey("scans.id"), unique=True, nullable=False)
    top_label = Column(String(100), nullable=False)  # e.g., "Pneumonia" or "Tumor"
    confidence = Column(Float, nullable=False)  # 0.0 – 1.0
    severity = Column(String(20), nullable=False)  # Normal, Mild, Moderate, Severe
    all_scores = Column(Text, nullable=False)  # JSON: {"Pneumonia": 0.87, ...}
    localization_type = Column(String(20), default="heatmap")  # "heatmap" or "bbox"
    bounding_boxes = Column(Text)  # JSON: [{"x1":89,"y1":120,...}, ...]
    analysis_time_ms = Column(Integer)
    analyzed_at = Column(DateTime, server_default=func.now())

    # Relationships
    scan = relationship("Scan", back_populates="result")

    def __repr__(self):
        return f"<Result(scan='{self.scan_id[:8]}', label='{self.top_label}', conf={self.confidence:.2f})>"


class Report(Base):
    """Generated clinical reports. One-to-one with analyzed scans."""
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scan_id = Column(String(36), ForeignKey("scans.id"), unique=True, nullable=False)
    patient_id = Column(String(50), default="DEMO-001")  # Placeholder for demo
    llm_provider = Column(String(20), default="template")  # groq, claude, openai, template
    report_json = Column(Text, nullable=False)  # Full structured report as JSON
    edited_findings = Column(Text)  # Clinician-edited findings (NULL until edited)
    edited_impression = Column(Text)  # Clinician-edited impression (NULL until edited)
    generated_at = Column(DateTime, server_default=func.now())

    # Relationships
    scan = relationship("Scan", back_populates="report")

    def __repr__(self):
        return f"<Report(scan='{self.scan_id[:8]}', provider='{self.llm_provider}')>"
