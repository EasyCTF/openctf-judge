from datetime import datetime, timedelta
from util import partial

from flask_sqlalchemy import SQLAlchemy
import requests
from sqlalchemy import and_, or_

import constants
import util

db = SQLAlchemy()


class APIKey(db.Model):
    __tablename__ = 'apikeys'
    id = db.Column(db.Integer, primary_key=True)
    active = db.Column(db.Boolean, default=True, nullable=False)
    name = db.Column(db.Unicode(length=16))
    key = db.Column(db.String(length=32), default=partial(util.generate_hex_string, 32), nullable=False)

    perm_jury = db.Column(db.Boolean, default=False, nullable=False)
    perm_reader = db.Column(db.Boolean, default=False, nullable=False)
    perm_master = db.Column(db.Boolean, default=False, nullable=False)

    @classmethod
    def new(cls, name=None, perm_jury=False, perm_reader=False, perm_master=False):
        api_key = APIKey(
            name=name,
            perm_jury=perm_jury,
            perm_reader=perm_reader,
            perm_master=perm_master,
        )
        db.session.add(api_key)
        db.session.commit()
        return api_key


class Problem(db.Model):
    __tablename__ = 'problems'
    id = db.Column(db.Integer, primary_key=True)
    last_modified = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    test_cases = db.Column(db.Integer, nullable=False)
    time_limit = db.Column(db.Float, nullable=False)
    memory_limit = db.Column(db.Integer, nullable=False)  # KB
    generator_code = db.Column(db.UnicodeText, nullable=False)
    generator_language = db.Column(db.Unicode(length=10), nullable=False)
    grader_code = db.Column(db.UnicodeText, nullable=False)
    grader_language = db.Column(db.Unicode(length=10), nullable=False)
    source_verifier_code = db.Column(db.UnicodeText)
    source_verifier_language = db.Column(db.Unicode(length=10))


class Submission(db.Model):
    __tablename__ = 'submissions'
    id = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.Integer)
    gid = db.Column(db.Integer)
    time = db.Column(db.DateTime, nullable=False)
    problem_id = db.Column(db.Integer, db.ForeignKey('problems.id'), nullable=False)
    problem = db.relationship('Problem', backref='submissions')
    code = db.Column(db.UnicodeText, nullable=False)
    language = db.Column(db.Unicode(length=10), nullable=False)

    @classmethod
    def create(cls, code, language, uid=None, gid=None, time=None, problem=None, commit=True):
        if time is None:
            time = datetime.utcnow()
        new_submission = cls(
            uid=uid,
            gid=gid,
            time=time,
            problem=problem,
            code=code,
            language=language,
        )
        db.session.add(new_submission)
        if commit:
            db.session.commit()
        return new_submission

    @classmethod
    def create_with_new_job(cls, code, language, uid=None, gid=None, time=None, problem=None, callback_url=None, commit=True):
        new_submission = cls.create(code=code, language=language, uid=uid, gid=gid, time=time, problem=problem,
                                    commit=False)
        new_job = Job.create(submission=new_submission, callback_url=callback_url, commit=False)
        if commit:
            db.session.commit()
        return new_submission, new_job

    @property
    def last_job(self):
        return self.jobs[-1]

    def generate_details(self, return_jobs=True):
        submission_details = util.get_attrs(self, ['id', 'uid', 'gid', 'time', 'problem_id', 'code', 'language'])
        if return_jobs:
            submission_details['jobs'] = [job.generate_details() for job in self.jobs]
        return submission_details


class Job(db.Model):
    __tablename__ = 'jobs'
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submissions.id'))
    submission = db.relationship('Submission', backref=db.backref('jobs',
                                                                  lazy='joined', order_by='Job.creation_time.asc()'))
    creation_time = db.Column(db.DateTime, index=True)
    status = db.Column(db.Enum(constants.JobStatus), nullable=False)
    claim_time = db.Column(db.DateTime, index=True)
    completion_time = db.Column(db.DateTime, index=True)

    # Must fill these if job started
    verification_code = db.Column(db.Integer())
    last_ran_case = db.Column(db.Integer)
    execution_time = db.Column(db.Float)  # max
    execution_memory = db.Column(db.Integer)  # KB

    verdict = db.Column(db.Enum(constants.JobVerdict))

    callback_url = db.Column(db.UnicodeText)

    @classmethod
    def create(cls, submission, creation_time=None, status=constants.JobStatus.queued, callback_url=None, commit=True):
        if creation_time is None:
            creation_time = datetime.utcnow()
        new_job = cls(
            submission=submission,
            creation_time=creation_time,
            status=status,

            callback_url=callback_url,
        )
        db.session.add(new_job)
        if commit:
            db.session.commit()
        return new_job

    @property
    def is_started(self):
        return self.status == constants.JobStatus.started or self.status == constants.JobStatus.finished

    @classmethod
    def query_can_claim(cls):
        return cls.query.filter(
            or_(
                Job.status == constants.JobStatus.queued,
                and_(
                    Job.status == constants.JobStatus.started,
                    Job.claim_time < datetime.utcnow() - timedelta(minutes=5)
                )
            )
        )

    def generate_details(self):
        return util.get_attrs(self, ['id', 'submission_id', 'creation_time', 'status', 'claim_time', 'completion_time',
                                     'last_ran_case', 'execution_time', 'execution_memory', 'verdict'],
                              include_none=False)

    def generate_claim_details(self):
        return {
            'id': self.id,
            'problem_id': self.submission.problem.id,
            'verification_code': self.verification_code,
            'code': self.submission.code,
            'language': self.submission.language,
        }

    def generate_verdict_details(self):
        return util.get_attrs(self, ['status', 'completion_time', 'last_ran_case', 'execution_time', 'execution_memory',
                                     'verdict'], include_none=False)

    def calculate_status_display(self):
        if self.status == constants.JobStatus.started:
            return 'Running on test case %d' % (self.last_ran_case + 1)
        if self.status == constants.JobStatus.finished:
            return self.verdict.value
        return self.status.value

    # This should be called asynchronously.
    def fire_callback(self):
        requests.post(self.callback_url, self.generate_details(), timeout=2)
