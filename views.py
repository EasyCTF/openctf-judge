import random
from datetime import datetime
from functools import wraps
import threading

from flask import current_app, Blueprint, json, make_response, render_template, request

import config
import constants
import util
from models import APIKey, db, Job, Problem, Submission
from sockets import socketio

blueprint = Blueprint('api', __name__)


def api_view(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        view_result = func(*args, **kwargs)
        return make_response(
            json.dumps(view_result[1], cls=util.JSONEncoder) if view_result[1] is not None else '',
            view_result[0],
            {'Content-Type': 'application/json; charset=utf-8'},
        )

    return wrapper


def require_perms(*perms):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if 'api_key' not in request.headers:
                return 403, None
            api_key = APIKey.query.filter_by(key=request.headers['api_key']).first()
            if not api_key or not api_key.active:
                return 403, None
            for permset in perms:
                if type(permset) == str:
                    if not getattr(api_key, 'perm_%s' % permset):
                        return 403, None
                elif type(permset) == tuple:
                    allowed = False
                    for perm in permset:
                        if getattr(api_key, 'perm_%s' % perm):
                            allowed = True
                    if not allowed:
                        return 403, None
            return func(*args, **kwargs)

        return wrapper

    return decorator


def need_send(obj):
    if 'If-Modified-Since' in request.headers and request.headers['If-Modified-Since']:
        given_timestamp = int(request.headers['If-Modified-Since'])
        if int(obj.last_modified.timestamp()) <= given_timestamp:
            return False
    return True


def socketio_emit(command, *args, rooms=None):
    if not current_app.config['ENABLE_SOCKETIO']:
        return

    if rooms:
        for room in rooms + ['monitor']:
            socketio.emit(command, args, room=room)
    else:
        socketio.emit(command, args)


def gen_errorhandler(error_code):
    @api_view
    def errorhandler(e):
        return error_code, None

    return errorhandler


def set_up_error_codes():
    for error_code in [400, 403, 404, 500]:
        blueprint.app_errorhandler(error_code)(gen_errorhandler(error_code))


set_up_error_codes()


@blueprint.route('/amisane')
@api_view
def sanity_check():
    return 200, None


@blueprint.route('/')
def monitor():
    return render_template('monitor.html')


@blueprint.route('/api_key', methods=['POST'])
@api_view
@require_perms('master')
def generate_api_key():
    perm_jury = request.form.get('jury', None) == 'true'
    perm_reader = request.form.get('jury', None) == 'true'
    api_key = APIKey.new(
        name=request.form.get('name', None),
        perm_jury=perm_jury,
        perm_reader=perm_reader,
        perm_master=False,  # explicitly do not allow master-key generation through web-facing api.
    )
    return 200, api_key.key


@blueprint.route('/submissions', methods=['GET'])
@api_view
@require_perms('reader')
def submissions_list():
    return 200, [submission.generate_details() for submission in Submission.query.all()]


@blueprint.route('/jobs', methods=['GET'])
@api_view
@require_perms('reader')
def jobs_list():
    return 200, [job.generate_details() for job in Job.query.all()]


@blueprint.route('/submissions/uid/<int:uid>', methods=['GET'])
@api_view
@require_perms('reader')
def submissions_list_by_uid(uid: int):
    return 200, [submission.generate_details() for submission in Submission.query.filter_by(uid=uid).all()]


@blueprint.route('/jobs/uid/<int:uid>', methods=['GET'])
@api_view
@require_perms('reader')
def jobs_list_by_uid(uid: int):
    return 200, [job.generate_details() for job in Job.query.join(Job.submission).filter_by(uid=uid).all()]


@blueprint.route('/submissions/gid/<int:gid>', methods=['GET'])
@api_view
@require_perms('reader')
def submissions_list_by_gid(gid: int):
    return 200, [submission.generate_details() for submission in Submission.query.filter_by(gid=gid).all()]


@blueprint.route('/jobs/gid/<int:gid>', methods=['GET'])
@api_view
@require_perms('reader')
def jobs_list_by_gid(gid: int):
    return 200, [job.generate_details() for job in Job.query.join(Job.submission).filter_by(gid=gid).all()]


@blueprint.route('/submissions/problem/<int:problem_id>', methods=['GET'])
@api_view
@require_perms('reader')
def submissions_list_by_problem(problem_id: int):
    return 200, [submission.generate_details() for submission in Submission.query.filter_by(problem_id=problem_id).all()]


@blueprint.route('/jobs/problem/<int:problem_id>', methods=['GET'])
@api_view
@require_perms('reader')
def jobs_list_by_problem(problem_id: int):
    return 200, [job.generate_details() for job in Job.query.join(Job.submission).filter_by(problem_id=problem_id).all()]


@blueprint.route('/submissions', methods=['POST'])
@api_view
@require_perms('reader')
def submissions_create():
    if not Problem.query.get(int(request.form['problem_id'])):
        return 400, 'Problem %d does not exist.' % int(request.form['problem_id'])

    if request.form['language'] not in config.SUPPORTED_LANGUAGES:
        return 400, 'Language %s not supported' % request.form['language']

    if 'callback_url' in request.form and len(request.form['callback_url']) > 256:
        return 400, 'Callback URL too long!'

    new_submission, new_job = Submission.create_with_new_job(
        uid=int(request.form['uid']) if 'uid' in request.form else None,
        gid=int(request.form['gid']) if 'gid' in request.form else None,
        time=datetime.utcnow(),
        problem=Problem.query.get(int(request.form['problem_id'])),
        code=request.form['code'],
        language=request.form['language'],

        callback_url=request.form.get('callback_url', None),
    )

    socketio_emit('submission_new', new_submission.id, rooms=['submissions'])
    socketio_emit('job_new', new_job.id, rooms=['jobs'])

    return 201, {'id': new_submission.id, 'job_id': new_job.id}


@blueprint.route('/submissions/<int:submission_id>/create_job', methods=['POST'])
@api_view
@require_perms('reader')
def submissions_job_create(submission_id):
    submission = Submission.query.get_or_404(submission_id)

    if 'callback_url' in request.form and len(request.form['callback_url']) > 256:
        return 400, 'Callback URL too long!'

    new_job = Job.create(
        submission=submission,

        callback_url=request.form.get('callback_url', None),
    )

    socketio_emit('job_new', new_job.id, rooms=['jobs', 'submission_{}'.format(submission_id)])

    return 201, {'job_id': new_job.id}


@blueprint.route('/jobs/claim', methods=['POST'])
@api_view
@require_perms('jury')
def jobs_claim():
    job = Job.query_can_claim().with_for_update().order_by(Job.creation_time.asc(), Job.id.asc()).first()
    if job is None:
        return 204, None
    job.status = constants.JobStatus.started
    job.claim_time = datetime.utcnow()
    verification_code = random.randint(1, 1000000000)
    job.verification_code = verification_code
    db.session.commit()
    job_details = job.generate_claim_details()

    socketio_emit('job_claimed', job.id, rooms=['job_{}'.format(job.id)])

    return 200, job_details


@blueprint.route('/jobs/<int:job_id>/release', methods=['POST'])
@api_view
@require_perms('jury')
def jobs_release(job_id: int):
    job = Job.query.with_for_update().get_or_404(job_id)
    if job.status != constants.JobStatus.started:
        return 409, None

    try:
        if job.verification_code and int(request.form['verification_code']) != job.verification_code:
            return 403, None
    except (ValueError, AttributeError):
        return 400, None

    job.status = constants.JobStatus.queued
    job.claim_time = None
    db.session.commit()

    socketio_emit('job_released', job.id, rooms=['job_{}'.format(job.id)])

    return 200, None


@blueprint.route('/submissions/<int:submission_id>', methods=['GET'])
@api_view
@require_perms('reader')
def submissions_details(submission_id: int):
    submission = Submission.query.get_or_404(submission_id)
    return 200, submission.generate_details()


@blueprint.route('/jobs/<int:job_id>', methods=['GET'])
@api_view
@require_perms('reader')
def jobs_status(job_id: int):
    job = Job.query.get_or_404(job_id)
    return 200, job.generate_details()


@blueprint.route('/jobs/<int:job_id>', methods=['DELETE'])
@api_view
@require_perms('reader')
def jobs_cancel(job_id: int):
    job = Job.query.with_for_update().get_or_404(job_id)
    if job.status == constants.JobStatus.finished or job.status == constants.JobStatus.cancelled:
        return 409, None
    job.status = constants.JobStatus.cancelled
    db.session.commit()

    socketio_emit('job_cancelled', job.id, ['job_{}'.format(job.id)])

    return 200, None


@blueprint.route('/jobs/<int:job_id>/submit', methods=['POST'])
@api_view
@require_perms('jury')
def jobs_submit(job_id: int):
    job = Job.query.with_for_update().get_or_404(job_id)

    if job.status != constants.JobStatus.started and job.status != constants.JobStatus.awaiting_verdict:
        return 409, 'Job not available for submission!'

    # TODO: Log warning is job can be submitted but does not have verification code.
    if job.verification_code and int(request.form['verification_code']) != job.verification_code:
        return 403, 'Incorrect verification code!'

    job.execution_time = float(request.form['execution_time'])
    job.execution_memory = int(request.form['execution_memory'])
    job.last_ran_case = int(request.form['last_ran_case'])

    # If cases already run await verdict.
    if job.last_ran_case == job.submission.problem.test_cases:
        job.status = constants.JobStatus.awaiting_verdict

    # Jury sends verdict to judge when judging is complete such as on TLE or AC.
    # Jury MUST send verdict after finishing all test cases.
    if 'verdict' in request.form and request.form['verdict']:
        job.verdict = constants.JobVerdict(request.form['verdict'])
        job.status = constants.JobStatus.finished
        job.completion_time = datetime.utcnow()
        job.verification_code = None

        threading.Thread(target=job.fire_callback).start()

    db.session.commit()

    socketio_emit('job_updated', job.id, json.dumps(job.generate_verdict_details()), rooms=['job_{}'.format(job.id)])

    return 200, None


@blueprint.route('/problems', methods=['GET'])
@api_view
@require_perms(('jury', 'reader'))
def problems_list():
    return 200, [util.column_dict(problem) for problem in Problem.query.all()]


@blueprint.route('/problems', methods=['POST'])
@api_view
@require_perms('reader')
def problems_create():
    problem_id = int(request.form['id'])
    if Problem.query.get(problem_id):
        return 409, None

    if request.form['generator_language'] not in config.SUPPORTED_LANGUAGES:
        return 400, 'Language %s not supported' % request.form['generator_language']
    if request.form['grader_language'] not in config.SUPPORTED_LANGUAGES:
        return 400, 'Language %s not supported' % request.form['grader_language']
    if 'source_verifier_language' in request.form and request.form[
        'source_verifier_language'] not in config.SUPPORTED_LANGUAGES:
        return 400, 'Language %s not supported' % request.form['source_verifier_language']

    new_problem = Problem(id=problem_id)
    for field in new_problem.__table__.columns:
        if field.name in ['id', 'last_modified']:
            continue
        if field.nullable:
            setattr(new_problem, field.name, request.form.get(field.name, None))
        else:
            setattr(new_problem, field.name, request.form[field.name])

    db.session.add(new_problem)
    db.session.commit()

    return 201, None


@blueprint.route('/problems/<int:problem_id>', methods=['GET'])
@api_view
@require_perms(('jury', 'reader'))
def problems_get(problem_id: int):
    problem = Problem.query.get_or_404(problem_id)
    if need_send(problem):
        return 200, util.column_dict(problem)
    else:
        return 304, None


@blueprint.route('/problems/<int:problem_id>', methods=['PUT'])
@api_view
@require_perms('reader')
def problems_modify(problem_id: int):
    problem = Problem.query.get_or_404(problem_id)
    for field in problem.__table__.columns:
        if field.name in ['id', 'last_modified']:
            continue
        if field.name in request.form:
            setattr(problem, field.name, request.form[field.name])

    db.session.commit()
    return 200, None
