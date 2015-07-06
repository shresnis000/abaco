import json

from flask_restful import Resource, Api

from models import Actor, Execution, Subscription
from request_utils import RequestParser, APIException
from stores import actors_store


class ActorsResource(Resource):

    def get(self):
        return [json.loads(actor[1]) for actor in actors_store.items()]

    def validate_post(self):
        parser = RequestParser()
        parser.add_argument('name', type=str, required=True, help="User defined name for this actor.")
        parser.add_argument('image', type=str, required=True,
                            help='Reference to image on docker hub for this actor.')
        parser.add_argument('description', type=str)
        args = parser.parse_args()
        return args

    def post(self):
        args = self.validate_post()
        actor = Actor(args)
        actors_store[actor.id] = actor.to_db()

        self.new_actor_message()
        return actor

    def new_actor_message(self):
        """Put a message on the new_actors queue that actor was created to create a new ActorExecutor for an actor."""
        # TODO
        pass


class ActorResource(Resource):
    def get(self, actor_id):
        try:
            actor = Actor.from_db(actors_store[actor_id])
        except KeyError:
            raise APIException(
                "actor not found: {}'".format(actor_id), 404)
        return actor

    def delete(self, actor_id):
        del actors_store[actor_id]
        self.delete_actor_message(actor_id)
        return {'msg': 'Delete successful.'}

    def put(self, actor_id):
        try:
            actor = Actor.from_db(actors_store[actor_id])
        except KeyError:
            raise APIException(
                "actor not found: {}'".format(actor_id), 404)
        args = self.validate_put()
        args['name'] = actor['name']
        args['id'] = actor['id']
        actor = Actor(args)
        actors_store[actor.id] = actor.to_db()
        self.update_actor_message(actor_id)
        return actor

    def validate_put(self):
        parser = RequestParser()
        parser.add_argument('image', type=str, required=True,
                            help='Reference to image on docker hub for this actor.')
        parser.add_argument('subscriptions', type=[str], help='List of event ids to subscribe this actor to.')
        parser.add_argument('description', type=str)
        args = parser.parse_args()
        return args

    def delete_actor_message(self, actor_id):
        """Put a command message on the actor_messages queue that actor was deleted."""
        # TODO
        pass

    def update_actor_message(self, actor_id):
        """Put a command message on the actor_messages queue that actor was updated."""
        # TODO
        pass


class ActorStateResource(Resource):
    def get(self, actor_id):
        try:
            actor = Actor.from_db(actors_store[actor_id])
            state = actor.get('state')
        except KeyError:
            raise APIException(
                "actor not found: {}'".format(actor_id), 404)
        return {'state': state }

    def post(self, actor_id):
        args = self.validate_post()
        state = args['state']
        try:
            actor = Actor.from_db(actors_store[actor_id])
        except KeyError:
            raise APIException(
                "actor not found: {}'".format(actor_id), 404)
        actor.state = state
        actors_store[actor_id] = actor.to_db()
        return actor

    def validate_post(self):
        parser = RequestParser()
        parser.add_argument('state', type=str, required=True, help="Set the state for this actor.")
        args = parser.parse_args()
        return args


class ActorSubscriptionResource(Resource):
    def get(self, actor_id):
        try:
            actor = Actor.from_db(actors_store[actor_id])
            subscriptions = actor.get('subscriptions') or {'subscriptions': None}
        except KeyError:
            raise APIException(
                "actor not found: {}'".format(actor_id), 404)
        return subscriptions

    def post(self, actor_id):
        args = self.validate_post()
        try:
            actor = Actor.from_db(actors_store[actor_id])
        except KeyError:
            raise APIException(
                "actor not found: {}'".format(actor_id), 404)
        event_ids = args['event_id']
        event_patterns = args['event_pattern']
        subs = {}
        for id in event_ids:
            s = Subscription(actor, {'event_id': id})
            subs[s.id] = s
            actor.subscriptions = subs
        for pat in event_patterns:
            s = Subscription(actor, {'event_pattern': pat})
            subs[s.id] = s
            actor.subscriptions = subs
        actors_store[actor_id] = actor.to_db()
        return actor

    def validate_post(self):
        parser = RequestParser()
        parser.add_argument('event_id', type=str, action='append', help="Event id for the subscription.")
        parser.add_argument('event_pattern', type=str, action='append', help="Regex pattern of event id's for the subscription.")
        args = parser.parse_args()
        return args


class ActorExecutionsResource(Resource):
    def get(self, actor_id):
        try:
            actor = Actor.from_db(actors_store[actor_id])
        except KeyError:
            raise APIException(
                "actor not found: {}'".format(actor_id), 404)
        tot = {'total_executions': 0, 'total_cpu': 0, 'total_io':0, 'total_runtime': 0, 'ids':[]}
        executions = actor.get('executions') or {}
        for id, val in executions.items():
            tot['ids'].append(id)
            tot['total_executions'] += 1
            tot['total_cpu'] += int(val['cpu'])
            tot['total_io'] += int(val['io'])
            tot['total_runtime'] += int(val['runtime'])
        return tot

    def post(self, actor_id):
        try:
            actor = Actor.from_db(actors_store[actor_id])
        except KeyError:
            raise APIException(
                "actor not found: {}'".format(actor_id), 404)
        args = self.validate_post()
        exc = Execution(actor, args)
        try:
            excs = actor.executions
        except KeyError:
            excs = {}
        excs[exc.id] = exc
        actor.executions = excs
        actors_store[actor_id] = actor.to_db()
        return actor

    def validate_post(self):
        parser = RequestParser()
        parser.add_argument('runtime', type=str, required=True, help="Runtime, in milliseconds, of the execution.")
        parser.add_argument('cpu', type=str, required=True, help="CPU usage, in user jiffies, of the execution.")
        parser.add_argument('io', type=str, required=True, help="Block I/O usage, in number of 512-byte sectors read from and written to, by the execution.")
        # Accounting for memory is quite hard -- probably easier to cap all containers at a fixed amount or perhaps have a graduated
        # list of cap sized (e.g. small, medium and large).
        # parser.add_argument('mem', type=str, required=True, help="Memory usage, , of the execution.")
        args = parser.parse_args()
        for k,v in args.items():
            try:
                int(v)
            except ValueError:
                raise APIException(message="Argument " + k + " must be an integer.")
        return args


class ActorExecutionResource(Resource):
    def get(self, actor_id, execution_id):
        try:
            actor = Actor.from_db(actors_store[actor_id])
        except KeyError:
            raise APIException(
                "actor not found: {}'".format(actor_id), 404)
        try:
            excs = actor.executions
        except KeyError:
            raise APIException("No executions found for actor {}.".format(actor_id))
        try:
            exc = excs[execution_id]
        except KeyError:
            raise APIException("Execution not found {}.".format(execution_id))
        return exc

