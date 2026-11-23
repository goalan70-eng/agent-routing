from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    operation: Literal['aggregate', 'share', 'trend', 'compare', 'rank', 'count', 'sum', 'mean'] = 'aggregate'
    group_by: tuple[str, ...] = Field(default=('region',), max_length=3)
    metric: str = Field(default='amount', max_length=100)
    filters: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    month_a: str | None = Field(default=None, pattern=r'^[0-9]{4}-(0[1-9]|1[0-2])$')
    month_b: str | None = Field(default=None, pattern=r'^[0-9]{4}-(0[1-9]|1[0-2])$')


class AnalystIntent(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    topic: str = Field(default='other', min_length=1, max_length=64, pattern=r'^[a-z][a-z0-9_]*$')
    goal: str | None = Field(default=None,max_length=500)
    start_month: str | None = Field(default=None,pattern=r'^[0-9]{4}-(0[1-9]|1[0-2])$')
    end_month: str | None = Field(default=None,pattern=r'^[0-9]{4}-(0[1-9]|1[0-2])$')
    nationality: str | None = Field(default=None,max_length=80)
    region: str | None = Field(default=None,max_length=80)
    customer: str | None = Field(default=None,max_length=80)
    industry: str | None = Field(default=None,max_length=80)
    operation: Literal['aggregate','compare','trend','rank','share'] | None = None
    change: Literal['none','year_ago','previous_month','graph','table'] = 'none'
    reset: bool = False
    data_source: Literal['auto','local_csv'] | None = None
    day_type: Literal['weekend','weekday','all'] | None = None
    task: Literal['explore','analyze'] | None = None
    focus: Literal['region','trend','customers'] | None = None

    @field_validator('data_source', mode='before')
    @classmethod
    def normalize_csv_source(cls, value):
        # Named CSV sources use the same local-file route.
        if isinstance(value, str) and value.endswith('_csv'):
            prefix = value[:-4]
            if prefix.isascii() and prefix.isidentifier() and prefix.islower() and len(prefix) <= 60:
                return 'local_csv'
        return value


class ChatDecision(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    action: Literal['reply', 'search', 'fetch', 'analyze', 'fetch_analyze', 'result', 'cancel', 'api_info', 'consult']
    reply: str = Field(default='', max_length=3000)
    query: str | None = Field(default=None, max_length=3000)
    dataset_id: str | None = Field(default=None, max_length=100)
    start_month: str | None = Field(default=None, pattern=r'^[0-9]{4}-(0[1-9]|1[0-2])$')
    end_month: str | None = Field(default=None, pattern=r'^[0-9]{4}-(0[1-9]|1[0-2])$')
    analysis: AnalysisRequest | None = None
    api_params: dict[str, str] | None = None
    intent: AnalystIntent | None = None

    @model_validator(mode='after')
    def consistent(self):
        if self.action == 'reply' and not self.reply.strip():
            raise ValueError('A reply must contain text.')
        if self.action == 'consult' and self.intent is None:
            raise ValueError('Semantic analyst intent is required.')
        if self.action in ('fetch', 'fetch_analyze', 'api_info') and not self.dataset_id:
            raise ValueError('A registered dataset ID is required.')
        if self.start_month and self.end_month and self.start_month > self.end_month:
            raise ValueError('The requested period is reversed.')
        if self.analysis and (len(self.analysis.filters) > 8 or any(len(v) > 100 for v in self.analysis.filters.values())):
            raise ValueError('Too many filters.')
        return self
