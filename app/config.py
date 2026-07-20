# Copyright (c) 2026-2027 宛皓 (Wan Hao). All rights reserved.
# 本文件为「云煤矿业产销量管理系统」的组成部分。
# 仅授予云南云煤矿业开发有限公司及其关联方在内部业务系统中使用；
# 未经著作权人书面同意，禁止复制、反编译、转售或二次发行。详见根目录 LICENSE。
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_base() -> Path:
    return Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    base_dir: Path = Field(default_factory=_default_base)
    secret_key: str = Field(
        default="dev-change-me-please-use-yml-or-env-YMKY_SECRET_KEY",
        min_length=16,
        description="Session signing key",
        validation_alias="YMKY_SECRET_KEY",
    )
    data_dir: Path | None = None
    database_url: str = Field(default="", validation_alias="DATABASE_URL")
    serverchan_sendkey: str = Field(default="", validation_alias="SERVERCHAN_SENDKEY")
    session_ttl_seconds: int = Field(default=8 * 3600, validation_alias="YMKY_SESSION_TTL")
    local_debug_password_autofill: bool = Field(
        default=False, validation_alias="YMKY_LOCAL_DEBUG"
    )
    # production 时对默认密钥等加强告警
    ymky_env: str = Field(default="development", validation_alias="YMKY_ENV")
    # 逗号分隔 Host 白名单；空则不做 Host 校验
    trusted_hosts: str = Field(default="", validation_alias="YMKY_TRUSTED_HOSTS")
    # 可选；暴露于 /health。若留空，则使用仓库 VERSION 文件（前缀 v）。
    app_version: str = Field(default="", validation_alias="YMKY_APP_VERSION")
    # 可选：三类角色密码（来自 .env）
    password_admin: str = Field(default="", validation_alias="YMKY_PASSWORD_ADMIN")
    password_reporter: str = Field(default="", validation_alias="YMKY_PASSWORD_REPORTER")
    password_viewer: str = Field(default="", validation_alias="YMKY_PASSWORD_VIEWER")

    @field_validator("ymky_env", mode="before")
    @classmethod
    def _coerce_ymky_env(cls, v: object) -> str:
        if v is None or (isinstance(v, str) and not v.strip()):
            return "development"
        s = str(v).strip().lower()
        if s in ("prod", "production"):
            return "production"
        return "development"

    @field_validator("local_debug_password_autofill", mode="before")
    @classmethod
    def _coerce_debug_bool(cls, v: object) -> bool:
        if v in (True, 1):
            return True
        if v in (False, 0, None, ""):
            return False
        if isinstance(v, str):
            return v.strip().lower() in ("1", "true", "yes", "on")
        return bool(v)
    optional_secrets_toml: Path | None = Field(
        default=None, description="Optional path to TOML with [passwords] block"
    )

    @model_validator(mode="after")
    def _resolve_paths(self) -> "Settings":
        d = self.data_dir or (self.base_dir / "data")
        object.__setattr__(self, "data_dir", Path(d).resolve())
        o = self.optional_secrets_toml
        if o is None:
            for cand in (
                self.base_dir / ".streamlit" / "secrets.toml",
                self.base_dir.parent / ".streamlit" / "secrets.toml",
            ):
                if cand.is_file():
                    object.__setattr__(self, "optional_secrets_toml", cand)
                    break
        return self

    @property
    def runtime_dir(self) -> Path:
        p = self.data_dir / "runtime"
        return p

    @property
    def actual_production_path(self) -> str:
        return str(self.data_dir / "actual_production.xlsx")

    @property
    def energy_reporting_path(self) -> str:
        return str(self.data_dir / "energy_reporting.xlsx")

    @property
    def sjcl_template(self) -> str:
        return str(self.data_dir / "sjcl.xlsx")

    @property
    def sjcl_template_v2(self) -> str:
        return str(self.data_dir / "sjcl1.xlsx")

    @property
    def nybb_template(self) -> str:
        return str(self.data_dir / "nybb.xlsx")

    @property
    def weeksheet_template(self) -> str:
        return str(self.data_dir / "weeksheet.xlsx")

    @property
    def actual_sales_path(self) -> str:
        return str(self.data_dir / "actual_sales.xlsx")

    @property
    def app_passwords_json(self) -> str:
        return str(self.runtime_dir / "app_passwords.json")

    @property
    def login_sessions_json(self) -> str:
        return str(self.runtime_dir / "login_sessions.json")

    @property
    def trusted_host_list(self) -> list[str]:
        raw = (self.trusted_hosts or "").strip()
        if not raw:
            return []
        return [x.strip() for x in raw.split(",") if x.strip()]

    @property
    def is_production(self) -> bool:
        return self.ymky_env == "production"


    @property
    def log_file(self) -> str:
        return self.data_dir / "ymky_system.log"


@lru_cache
def get_settings() -> Settings:
    return Settings()
