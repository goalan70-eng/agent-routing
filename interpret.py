from decision import ChatDecision


class ModelError(RuntimeError):
    def __init__(self, message, code='MODEL_ERROR'):
        super().__init__(message)
        self.code = code


class PublicInterpreter:
    def __init__(self):
        self.usage = dict(calls=0, prompt_tokens=0, completion_tokens=0)
        self.last_model_provider = None
        self.last_model_completion = None

    def _interpret_public(self, provider, messages, on_event, cancel_event):
        self.last_model_provider = 'openai'
        if on_event is not None:
            on_event('OPENAI_RUNNING', '공개 자료에 대한 질문을 해석하고 있습니다.')
        self.usage['calls'] += 1
        completion = provider.complete(messages, cancel_event=cancel_event)
        self.last_model_completion = completion
        self.usage['prompt_tokens'] += completion.prompt_tokens
        self.usage['completion_tokens'] += completion.completion_tokens
        if on_event is not None:
            on_event('VALIDATING_MODEL', '공개 조회 제안을 검증하고 있습니다.')
        if cancel_event is not None and cancel_event.is_set():
            raise ModelError('GPT 요청을 취소했습니다. 도착한 제안은 적용하지 않습니다.', 'MODEL_CANCELLED')
        return ChatDecision.model_validate_json(completion.content)
