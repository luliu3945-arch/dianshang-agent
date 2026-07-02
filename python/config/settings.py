from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "Multi-Agent E-Commerce System"
    debug: bool = False

    # LLM
    llm_api_key: str = ""
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    # 三类LLM任务(画像分析/排序/文案)均为结构化输出，轻量模型即可胜任；
    # 推理类模型(glm-5等)的思考token会使单次调用达30-40s，与推荐场景的延迟要求不匹配
    llm_model: str = "qwen-flash"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 2048

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    feature_ttl_seconds: int = 86400

    # Milvus
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_collection: str = "product_embeddings"

    # Database
    database_url: str = "sqlite:///./ecommerce.db"

    # A/B Testing
    ab_test_enabled: bool = True
    ab_test_default_bucket_count: int = 100

    # Agent timeouts (seconds)
    # 按qwen-flash实测延迟(1-3s)设定，留5倍余量；
    # 若改用推理类模型(如glm-5，单次30-40s)需相应上调
    agent_timeout_user_profile: float = 15.0
    agent_timeout_product_rec: float = 15.0
    agent_timeout_marketing_copy: float = 15.0
    agent_timeout_inventory: float = 5.0

    model_config = {"env_file": ".env", "env_prefix": "ECOM_"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
