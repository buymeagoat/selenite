import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now, onupdate=_now)

    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="artifact", cascade="all, delete-orphan")
    tags: Mapped[list["Tag"]] = relationship("Tag", secondary="artifact_tags", back_populates="artifacts")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    artifact_id: Mapped[str] = mapped_column(String, ForeignKey("artifacts.id"), nullable=False)
    stage: Mapped[str] = mapped_column(String, nullable=False)
    stage_task: Mapped[str | None] = mapped_column(String, nullable=True)
    processor: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="queued")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now, onupdate=_now)

    artifact: Mapped["Artifact"] = relationship("Artifact", back_populates="jobs")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    color: Mapped[str] = mapped_column(String, nullable=False, default="#F5A623")

    artifacts: Mapped[list["Artifact"]] = relationship("Artifact", secondary="artifact_tags", back_populates="tags")


class ArtifactTag(Base):
    __tablename__ = "artifact_tags"
    __table_args__ = (UniqueConstraint("artifact_id", "tag_id"),)

    artifact_id: Mapped[str] = mapped_column(String, ForeignKey("artifacts.id"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(Integer, ForeignKey("tags.id"), primary_key=True)


class Config(Base):
    __tablename__ = "config"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
