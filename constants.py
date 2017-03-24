import enum


class APIKeyType(enum.Enum):
    jury = 'jury'
    observer = 'observer'


class JobStatus(enum.Enum):
    queued = 'queued'
    cancelled = 'cancelled'
    started = 'started'
    awaiting_verdict = 'awaiting_verdict'
    finished = 'finished'


class JobVerdict(enum.Enum):
    accepted = 'AC'
    ran = 'RAN'
    invalid_source = 'IS'
    wrong_answer = 'WA'
    time_limit_exceeded = 'TLE'
    memory_limit_exceeded = 'MLE'
    runtime_error = 'RTE'
    illegal_syscall = 'ISC'
    compilation_error = 'CE'
    judge_error = 'JE'
