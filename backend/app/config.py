"""应用配置：从环境变量加载，使用 pydantic-settings 校验."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """统一配置入口."""

    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ==================== 应用 ====================
    APP_ENV: Literal["local", "dev", "staging", "prod"] = "local"
    APP_DEBUG: bool = True
    APP_NAME: str = "xiaoniao-ai"
    APP_SECRET_KEY: str = "change-me"
    APP_LOG_LEVEL: str = "INFO"

    # ==================== 后端服务 ====================
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    BACKEND_WORKERS: int = 1
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000,http://localhost:10086"
    # 客户端访问 backend 的对外基址（含 scheme + host + port，不含 /v1）。
    # 用于生成需要返回给客户端的"同源代理 URL"（如 keyframe 图片代理），
    # 解决微信小程序真机 <Image> 对 MinIO 9000 端口 HTTP 资源的拒绝问题。
    # W8 真机模式：http://192.168.130.37:8000；线上：https://api.xxx.com
    API_PUBLIC_BASE_URL: str = "http://localhost:8000"

    # ==================== JWT ====================
    JWT_SECRET_KEY: str = "change-me-jwt"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_DAYS: int = 7

    # ==================== PostgreSQL ====================
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "xiaoniao"
    POSTGRES_PASSWORD: str = "xiaoniao_dev_password"
    POSTGRES_DB: str = "xiaoniao"
    DATABASE_URL: str = ""
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # ==================== Redis ====================
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_URL: str = ""

    # ==================== 对象存储 ====================
    STORAGE_PROVIDER: Literal["minio", "cos"] = "minio"
    MINIO_ENDPOINT: str = "http://minio:9000"
    MINIO_PUBLIC_ENDPOINT: str = "http://localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "xiaoniao-videos"
    MINIO_REGION: str = "us-east-1"

    # 腾讯云 COS（S3 兼容，使用 MinIO Python 客户端对 cos.*.myqcloud.com 签名，需桶公共读/跨域在控制台配置）
    COS_SECRET_ID: str = ""
    COS_SECRET_KEY: str = ""
    COS_REGION: str = "ap-shanghai"
    COS_BUCKET: str = ""  # 形如 mybucket-1250000000
    COS_PUBLIC_BASE: str = ""  # 可选；默认 https://{bucket}.cos.{region}.myqcloud.com

    # ==================== 微信小程序 ====================
    WECHAT_MINIPROGRAM_APPID: str = "wx_placeholder_appid"
    WECHAT_MINIPROGRAM_SECRET: str = "placeholder_secret"
    WECHAT_MOCK_LOGIN: bool = True
    # 一次性订阅消息：分析完成等场景调用 subscribeMessage.send；默认关闭，避免模板未对齐时报错
    WECHAT_SUBSCRIBE_MESSAGE_ENABLED: bool = False
    # 须与公众平台模板 ID、客户端 TARO_APP_SUBSCRIBE_TMPL_IDS 首项一致
    WECHAT_SUBSCRIBE_ANALYSIS_TEMPLATE_ID: str = ""
    # 下发一次性订阅消息时的小程序版本：须与当前分发渠道一致
    WECHAT_SUBSCRIBE_MINIPROGRAM_STATE: Literal["developer", "trial", "formal"] = "developer"
    # 须与客户端 TARO_APP_SUBSCRIBE_TMPL_IDS 第二项一致（会员到期提醒）
    WECHAT_SUBSCRIBE_MEMBERSHIP_EXPIRE_TEMPLATE_ID: str = ""
    # 第三项：会员「即将到期」（日历剩余天数 ∈ MEMBERSHIP_PRE_EXPIRY_NOTIFY_DAYS）预提醒
    WECHAT_SUBSCRIBE_MEMBERSHIP_PRE_EXPIRE_TEMPLATE_ID: str = ""
    # 「到期日当天之前」的第 N 个日历日（按 Asia/Shanghai）尝试发第三模板，每日 Celery 扫一次。
    # 历史单档：``"3"``；多档（产品 §3.5 多档提醒）：``"7,3,1"``。空串 / `"0"` 关闭任务。
    # 注意：每档独立 Redis 去重（key 含 days），同一用户 7/3/1 三档下用户须分别授权三次才有 3 次发送配额。
    MEMBERSHIP_PRE_EXPIRY_NOTIFY_DAYS: str = "3"

    # ==================== 微信开放平台（App） ====================
    WECHAT_OPEN_APPID: str = ""
    WECHAT_OPEN_SECRET: str = ""

    # ==================== 微信支付 ====================
    # W7-T1 默认 mock。正式版：WECHAT_PAY_MOCK_MODE=false 并填全商户、证书、APIv3 密钥与公网 notify_url
    WECHAT_PAY_MOCK_MODE: bool = True
    WECHAT_PAY_MCH_ID: str = ""
    # APIv3 密钥 32 字符（与商户平台「API 安全>APIv3 密钥」一致）
    WECHAT_PAY_API_V3_KEY: str = ""
    # 兼容历史命名：与 WECHAT_PAY_API_V3_KEY 二选一
    WECHAT_PAY_API_KEY: str = ""
    # 商户 API 私钥 PEM 路径（apiclient_key.pem）
    WECHAT_PAY_CERT_PATH: str = ""
    # 或直接把 PEM 内容放此字段（K8s Secret 注入时），有值则优先生效于 `WECHAT_PAY_CERT_PATH`
    WECHAT_PAY_PRIVATE_KEY_PEM: str = ""
    # 商户 API 证书「序列号」（用于 Authorization: serial_no）
    WECHAT_PAY_MCH_SERIAL: str = ""
    # 小程序支付成功异步通知，须 HTTPS 公网，路径示例 /v1/payments/wechat/notify
    WECHAT_PAY_NOTIFY_URL: str = ""
    # 退款结果异步通知完整 HTTPS URL；为空时在 WECHAT_PAY_NOTIFY_URL 上推导
    # `/v1/payments/wechat/notify` → `/v1/payments/wechat/refund-notify`
    WECHAT_PAY_REFUND_NOTIFY_URL: str = ""
    # MVP：支付成功后该小时内允许自助全额退款（0 关闭时间窗校验，仅面向测试）
    PAYMENT_SELF_REFUND_WINDOW_HOURS: int = 24

    # 待支付订单超过该分钟数自动置为 cancelled（定时任务：`xiaoniao.expire_stale_pending_orders`）
    PAYMENT_PENDING_ORDER_EXPIRE_MINUTES: int = 120

    # Q-B5：微信委托代扣（预约扣费）模板 ID，商户平台申请后填入；0 表示未开通能力
    WECHAT_PAY_PAPAY_PLAN_ID: int = 0
    # 委托代扣签约结果通知 URL（HTTPS，可与支付 notify 不同路径）；须登记到商户平台
    WECHAT_PAY_PAPAY_NOTIFY_URL: str = ""

    # ==================== 微信小程序虚拟支付（xpay） ====================
    # iOS 虚拟会员须走 wx.requestVirtualPayment；审核通过后在 mp 后台配置道具与 appKey
    WECHAT_XPAY_ENABLED: bool = False
    WECHAT_XPAY_OFFER_ID: str = ""
    WECHAT_XPAY_APP_KEY: str = ""
    WECHAT_XPAY_SANDBOX_APP_KEY: str = ""
    # 0 现网 1 沙箱（须与 appKey 成对）
    WECHAT_XPAY_ENV: int = 0
    WECHAT_XPAY_PRODUCT_MONTHLY: str = ""
    WECHAT_XPAY_PRODUCT_YEARLY: str = ""

    # 小程序消息推送（接收 xpay_goods_deliver_notify 等 Event）
    WECHAT_MP_PUSH_TOKEN: str = ""
    WECHAT_MP_PUSH_ENCODING_AES_KEY: str = ""

    # ==================== 苹果内购 ====================
    APPLE_BUNDLE_ID: str = "com.xiaoniaoai.app"
    APPLE_SHARED_SECRET: str = ""
    APPLE_VERIFY_RECEIPT_URL: str = "https://sandbox.itunes.apple.com/verifyReceipt"

    # ==================== LLM ====================
    LLM_PROVIDER: Literal["deepseek", "qwen", "glm", "openai"] = "deepseek"
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.deepseek.com/v1"
    LLM_MODEL: str = "deepseek-chat"
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 2000
    # 流式读：控制在「相邻两次 chunk 间隔」阈值；首轮排队长 + 文末 token 慢的模型需要 ≥90s。
    LLM_TIMEOUT_SECONDS: int = 120
    # 连接层抖动 / 服务商 429·502·503·504：整流重来（首张 token 未到前且不破坏已输出片段）。
    LLM_HTTP_MAX_RETRIES: int = 2
    LLM_HTTP_RETRY_BACKOFF_BASE: float = 0.75
    LLM_MOCK_MODE: bool = False  # True 强制 FakeLLM；False 且 API_KEY 为空时也自动回退 Fake

    # ==================== AI Engine ====================
    AI_ENGINE_URL: str = "http://ai_engine:9000"
    # W6-T4：从 120s 降到 60s。docs/01 §4.2 用户最大容忍 120s（含网络回程 / Celery 调度
    # 排队），ai_engine 真实引擎 CPU 预算 30s（preprocess 5 + pose 12 + 其它 13），
    # 留 2x buffer = 60s。降下来可以更快感知到挂死任务，触发 _mark_failed + 退配额。
    AI_ENGINE_TIMEOUT: int = 60
    # O-08：引擎快速预检（含下载 + ≤5s 扫描）；默认略大于全量 analyze
    AI_ENGINE_PRECHECK_TIMEOUT: int = 20
    # backend 不直接消费这个变量（只在 ai_engine 容器内决定走 mock or real），
    # 留在这里仅为 .env.local 校验完整性 + 便于将来 backend 侧加 fallback 逻辑
    AI_ENGINE_MOCK_MODE: bool = False

    # ==================== Phase 2 灰度开关 ====================
    # M9 画像 2.0（user_profiles_v2 + user_clubs + onboarding + 目标偏好/LLM 注入）；
    # 默认 false，M9-02 UI 上线时切 true。关闭时：路由层 404 不暴露字段；
    # M9-04 LLM prompt 注入也短路（chat_service 拉 V2 profile 前判断此 flag）。
    PHASE2_PROFILE_V2_ENABLED: bool = False

    # M11 课程体系（courses/lessons/user_course_progress/course_certificates）；
    # 默认 false，M11-03 学习路径 UI 上线时切 true。
    PHASE2_COURSES_ENABLED: bool = False

    # M11-06 教练定制课程写端点；M8 教练认证就位前用 user_id 白名单（逗号分隔 usr_xxx）。
    # 空字符串 = 无人可写（端点仍 404/403，不暴露存在性给非白名单）。
    COACH_COURSE_USER_IDS: str = ""

    # M8-01 教练档案 / 资质审核；默认 false。
    PHASE2_COACH_ENABLED: bool = False
    # M8-01 Admin 审核端点白名单（逗号分隔 usr_xxx）；CI / 本地联调可配置。
    ADMIN_USER_IDS: str = ""

    # M12 球手对比库（pro_players + pro_swing_clips 等 6 张表）；默认 false，
    # M12-03 资源库 tab UI 上线时切 true。
    PHASE2_PROS_ENABLED: bool = False

    # M8-04 / M12-09 教练报告批注（video_ref 等）；默认 false。
    PHASE2_COACH_ANNOTATIONS_ENABLED: bool = False

    # M8-05 教练作业派发；默认 false。
    PHASE2_COACH_TASKS_ENABLED: bool = False
    COACH_TASK_MAX_PER_DAY: int = 50

    # M8-06 教练学员看板；默认 false。
    PHASE2_COACH_DASHBOARD_ENABLED: bool = False

    # M8-07 教练教学报告（LLM 汇总 + PDF）；默认 false。
    PHASE2_COACH_RECAP_ENABLED: bool = False
    COACH_RECAP_PDF_URL_TTL_SECONDS: int = 86400

    # M8-08 教练 UGC 内容审核；默认 false（关闭时保持 M8-04 自动 approved）。
    PHASE2_COACH_CONTENT_MODERATION_ENABLED: bool = False
    CONTENT_MODERATION_PROVIDER: str = "mock"
    CONTENT_MODERATION_TIMEOUT_SEC: int = 3
    CONTENT_MODERATION_SLA_HOURS: int = 24

    # M8-09 教练角色免扣配额 + 日限风控。
    COACH_QUOTA_BYPASS_ENABLED: bool = True
    COACH_ANALYSIS_DAILY_LIMIT: int = 1000
    COACH_CHAT_DAILY_LIMIT: int = 2000

    # M13 球友约球
    # 上线前需 DEP-05 法律意见书到位（M13-09 服务协议 / 未成年保护）。
    PHASE2_MEETUP_ENABLED: bool = False
    # M13-09：mock 登录用户自动补齐成年实名（CI / 本地）；生产须 false
    MEETUP_MOCK_IDENTITY_VERIFIED: bool = True

    # M13-06 约球风控阈值（可被 Redis meetup:risk:config 覆盖）
    MEETUP_RISK_DAILY_LIMIT_FREE: int = 5
    MEETUP_RISK_DAILY_LIMIT_MEMBER: int = 10
    MEETUP_RISK_ACCEPT_RATE_THRESHOLD: float = 0.10
    MEETUP_RISK_ACCEPT_RATE_MIN_SAMPLES: int = 10
    MEETUP_RISK_CONSECUTIVE_DECLINE_LIMIT: int = 3
    MEETUP_RISK_COOLDOWN_HOURS: int = 24
    MEETUP_RISK_CREDIT_MIN_TO_INVITE: int = 60

    # ==================== 业务规则 ====================
    FREE_USER_MONTHLY_ANALYSES: int = 3
    FREE_USER_DAILY_CHATS: int = 5
    MAX_VIDEO_DURATION_SECONDS: int = 30
    MIN_VIDEO_DURATION_SECONDS: int = 3
    MAX_VIDEO_SIZE_BYTES: int = 100 * 1024 * 1024  # 100MB

    # ==================== W8-T3：测试期配额放宽 ====================
    # `strict`：按 FREE_USER_* 严格扣减（生产 / 默认）
    # `unlimited`：所有 consume_* 直接放行，所有 get_* 返回 -1（无限）；
    #              专用于 W8 内测环境，避免内测团队被 3 次 / 5 次卡死
    # 切换不影响付费会员（会员本来就 -1），只影响免费用户
    QUOTA_MODE: Literal["strict", "unlimited"] = "strict"

    # ==================== Sentry（监控告警；PMF 阶段必装） ====================
    # DSN 为空 → ``setup_sentry()`` 直接 no-op，本地开发与 CI 不需要配置；
    # 生产环境填上 Sentry 项目 DSN 后 backend / Celery 异常会自动上报。
    SENTRY_DSN: str = ""
    # 性能采样率（0.0~1.0）。MVP 期建议 0.0（不发性能事件）或 0.05（小流量采样）；
    # 仅捕获异常 + 慢请求即足以排障，全量 trace 会快速吃掉 Sentry 免费额度。
    SENTRY_TRACES_SAMPLE_RATE: float = 0.0
    # 仅对未捕获异常生效；profile 同理保留为 0，避免误吞额度。
    SENTRY_PROFILES_SAMPLE_RATE: float = 0.0
    # 上报的 environment 标签；不设则用 APP_ENV（local / dev / staging / prod）。
    SENTRY_ENVIRONMENT: str = ""
    # 版本号；不设则用 app.__version__；CD 流水线可注入 git short SHA 便于灰度对比。
    SENTRY_RELEASE: str = ""
    # 发送 PII（IP / 用户 ID 等）：MVP 期默认 False 走合规保守，
    # 仅在排障某具体用户时临时打开（仍受 PIPL §47 的最小必要原则约束）。
    SENTRY_SEND_DEFAULT_PII: bool = False

    @property
    def database_url(self) -> str:
        """优先使用显式 DATABASE_URL，否则按字段组装."""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def database_url_sync(self) -> str:
        """同步版连接串，给 Alembic 用."""
        url = self.database_url
        return url.replace("+asyncpg", "+psycopg2") if "+asyncpg" in url else url

    @property
    def redis_url(self) -> str:
        """组装 Redis URL."""
        if self.REDIS_URL:
            return self.REDIS_URL
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    @property
    def cors_origins_list(self) -> list[str]:
        """CORS origins 解析为列表."""
        return [o.strip() for o in self.BACKEND_CORS_ORIGINS.split(",") if o.strip()]

    @property
    def cors_allow_origins(self) -> list[str]:
        """`CORSMiddleware.allow_origins` 用。

        历史上 `cors_origins_list` 为空时曾退回 ``*``，浏览器任意 Origin 均可读 API。
        生产且未显式配置时改为空列表（配合小程序主要走服务端、H5 管理台应显式填域）。
        """
        raw = self.cors_origins_list
        if raw:
            return raw
        if self.is_prod:
            return []
        return [
            "http://localhost:3000",
            "http://localhost:10086",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:10086",
        ]

    @property
    def is_local(self) -> bool:
        return self.APP_ENV == "local"

    @property
    def is_prod(self) -> bool:
        return self.APP_ENV == "prod"

    @staticmethod
    def _is_placeholder_minio_public(endpoint: str) -> bool:
        """仍为 Docker/本地默认时，签发 upload_url 会踩微信小程序合法域名校验。"""
        e = endpoint.strip().rstrip('/').lower()
        return e in (
            "",
            'http://localhost:9000',
            'http://127.0.0.1:9000',
            'http://minio:9000',
        )

    @property
    def effective_minio_public_endpoint(self) -> str:
        """发给客户端（wx.uploadFile）的 MinIO/S3 POST 基准地址（不含路径时由后端拼 bucket）。

        staging/prod 常见疏漏：`API_PUBLIC_BASE_URL` 已是 `https://api.xxx`，
        `MINIO_PUBLIC_ENDPOINT` 却留在默认 `localhost:9000`，导致小程序仍向未登记域名直传。
        此时按网关反代惯例回退到 `{API_PUBLIC_BASE_URL}/minio`。
        （须与 nginx/COS 反代路由一致；仅当 `MINIO_PUBLIC_ENDPOINT` 仍为占位值时启用。）

        COS 或其它显式非公网占位配置：仍使用 `MINIO_PUBLIC_ENDPOINT` 原值。"""
        raw = self.MINIO_PUBLIC_ENDPOINT.strip()
        if self.STORAGE_PROVIDER != "minio":
            return raw
        if self.APP_ENV not in {"staging", "prod"}:
            return raw
        if not self._is_placeholder_minio_public(raw):
            return raw
        api = self.API_PUBLIC_BASE_URL.strip().rstrip('/')
        if not api.lower().startswith("https://"):
            return raw
        if 'localhost' in api.lower() or '127.0.0.1' in api:
            return raw
        return f"{api}/minio"

    @property
    def effective_api_public_base_url(self) -> str:
        """后端对客户端可见的根地址（scheme+host[+port]，无尾 slash）。

        `/v1` 前缀由客户端拼接；`/v1/assets/image` 图片代理与它同源，
        「request / downloadFile（走 API）」的合法域名必须与这里的主机一致。
        """
        return self.API_PUBLIC_BASE_URL.strip().rstrip("/")

    @property
    def storage_presign_origin_base(self) -> str:
        """直传视频的 presigned POST 基准（与 integrations/minio 内分支逻辑保持一致）。

        - MinIO：`effective_minio_public_endpoint`
        - COS：`COS_PUBLIC_BASE` 缺省则为 `https://cos.<region>.myqcloud.com`

        「uploadFile 合法域名」须覆盖此处解析出的 **https 主机**（若与 API 不同须分别登记）。
        """
        if self.STORAGE_PROVIDER == "cos":
            internal = f"https://cos.{self.COS_REGION}.myqcloud.com"
            base = self.COS_PUBLIC_BASE.strip().rstrip("/") if self.COS_PUBLIC_BASE else ""
            return base or internal
        return self.effective_minio_public_endpoint.strip().rstrip("/")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """单例配置."""
    return Settings()


settings = get_settings()
