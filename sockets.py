"""
Command handlers for SocketIO.

There is a race condition in the subscription commands for specific objects, as updates to the item may be
emitted before its initial data, which might or might not have that update already applied to it. Clients should
keep a buffer of updates to apply to the object when it is received if the object has not already been received.
Because of the race potential between update emissions and initial objects, the object is queried for existence
(and potentially permission) once from the SQL database, then the subscriber is added to the room, and then
the object is queried for again and emitted to the subscriber.
"""

from flask import current_app, json
from flask_socketio import SocketIO, emit, leave_room, join_room

from models import db, Job, Submission

socketio = SocketIO()


@socketio.on('sub_monitor')
def sub_monitor():
    join_room('monitor')


@socketio.on('sub_jobs')
def sub_jobs():
    join_room('jobs')


@socketio.on('unsub_jobs')
def unsub_jobs():
    leave_room('jobs')


@socketio.on('sub_job')
def sub_job(job_id):
    job_exists = db.session.query(Job.query.filter_by(id=job_id).exists()).scalar()
    if not job_exists:
        emit('error', 'sub_job', 'Job does not exist!')
        return
    join_room('job_{}'.format(int(job_id)))
    job = Job.query.get(job_id)
    if not job:
        current_app.logger.warning('Job {} disappeared after existence check in sub_job'.format(job_id))
        emit('error', 'sub_job', 'Job does not exist!')
        return
    emit('job_init', json.dumps(job.generate_details()))


@socketio.on('unsub_job')
def unsub_job(job):
    leave_room('job_{}'.format(int(job)))


@socketio.on('sub_submissions')
def sub_submissions():
    join_room('submissions')


@socketio.on('unsub_submissions')
def unsub_submissions():
    leave_room('submissions')


@socketio.on('sub_submission')
def sub_submission(submission_id):
    submission_exists = db.session.query(Submission.query.filter_by(id=submission_id).exists()).scalar()
    if not submission_exists:
        emit('error', 'sub_submission', 'Submission does not exist!')
        return
    join_room('submission_{}'.format(int(submission_id)))
    submission = Submission.query.get(submission_id)
    if not submission:
        current_app.logger.warning('Submission {} disappeared after existence check in sub_submission'.format(submission_id))
        emit('error', 'sub_submission', 'Submission does not exist!')
        return
    emit('submission_init', json.dumps(submission.generate_details()))


@socketio.on('unsub_submission')
def unsub_submission(submission):
    leave_room('submission_{}'.format(int(submission)))
