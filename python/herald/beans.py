#!/usr/bin/python
# -- Content-Encoding: UTF-8 --
"""
Herald core beans definition

:author: Thomas Calmant
:copyright: Copyright 2014, isandlaTech
:license: Apache License 2.0
:version: 0.0.3
:status: Alpha

..

    Copyright 2014 isandlaTech

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
"""

# Module version
__version_info__ = (0, 0, 3)
__version__ = ".".join(str(x) for x in __version_info__)

# Documentation strings format
__docformat__ = "restructuredtext en"

# ------------------------------------------------------------------------------

# Standard library
import functools
import threading
import time
import uuid
import json

# ------------------------------------------------------------------------------


@functools.total_ordering
class Peer(object):
    """
    Represents a peer in Herald
    """
    def __init__(self, uid, node_uid, app_id, groups, directory):
        """
        Sets up the peer

        :param uid: Peer Unique ID
        :param node_uid: Node Unique ID
        :param app_id: Peer Application ID
        :param groups: The list of groups this peer belongs to
        :param directory: Directory to call back on access update
        :raise ValueError: Invalid Peer UID
        """
        if not uid:
            raise ValueError("The UID of a peer can't be empty")

        self.__uid = uid
        self.__name = uid
        self.__node = node_uid or uid
        self.__node_name = self.__node
        self.__app_id = app_id
        self.__groups = set(groups or [])
        self.__accesses = {}
        self.__directory = directory
        self.__lock = threading.RLock()

    def __repr__(self):
        """
        Peer representation
        """
        return "Peer({0})".format(self.__uid)

    def __str__(self):
        """
        Peer pretty representation
        """
        if self.__name and self.__name != self.__uid:
            return "{0} ({1})".format(self.__name, self.__uid)
        else:
            return self.__uid

    def __hash__(self):
        """
        Use the UID string hash as bean hash
        """
        return hash(self.__uid)

    def __eq__(self, other):
        """
        Equality is based on the UID
        """
        if isinstance(other, Peer):
            return self.__uid == other.uid
        return False

    def __lt__(self, other):
        """
        Ordering is based on the UID
        """
        if isinstance(other, Peer):
            return self.__uid < other.uid
        return False

    @property
    def uid(self):
        """
        Retrieves the UID of the peer
        """
        return self.__uid

    @property
    def app_id(self):
        """
        Returns the ID of the application this peer is part of
        """
        return self.__app_id

    @property
    def name(self):
        """
        Retrieves the name of the peer
        """
        return self.__name

    @name.setter
    def name(self, value):
        """
        Sets the name of the peer

        :param value: A peer name
        """
        self.__name = value or self.__uid

    @property
    def node_uid(self):
        """
        Retrieves the UID of the node hosting the peer
        """
        return self.__node

    @property
    def node_name(self):
        """
        Retrieves the name of the node hosting the peer
        """
        return self.__node_name

    @node_name.setter
    def node_name(self, value):
        """
        Sets the name of the node hosting the peer

        :param value: A node name
        """
        self.__node_name = value or self.__node

    @property
    def groups(self):
        """
        Retrieves the set of groups this peer belongs
        """
        return self.__groups.copy()

    def __callback(self, method_name, *args):
        """
        Calls back the associated directory

        :param method_name: Name of the method to call
        :param args: Arguments of the method to call back
        """
        try:
            method = getattr(self.__directory, method_name)
        except AttributeError:
            # Directory not available/not fully implemented
            pass
        else:
            # Always give this bean as first parameter
            return method(self, *args)

    def dump(self):
        """
        Dumps the content of this Peer into a dictionary

        :return: A dictionary describing this peer
        """
        # Properties
        dump = {name: getattr(self, name)
                for name in ('uid', 'name', 'node_uid', 'node_name',
                             'app_id', 'groups')}

        # Accesses
        dump['accesses'] = {access: data.dump()
                            for access, data in self.__accesses.items()}
        return dump

    def get_access(self, access_id):
        """
        Retrieves the description of the access stored with the given ID

        :param access_id: An access ID (xmpp, http, ...)
        :return: The description associated to the given ID
        :raise KeyError: Access not described
        """
        return self.__accesses[access_id]

    def get_accesses(self):
        """
        Returns the list of access IDs associated to this peer

        :return: A list of access IDs
        """
        return tuple(self.__accesses)

    def has_access(self, access_id):
        """
        Checks if the access is described

        :param access_id: An access ID
        :return: True if the access is described
        """
        return access_id in self.__accesses

    def has_accesses(self):
        """
        Checks if the peer has any access

        :return: True if the peer has at least one access
        """
        return bool(self.__accesses)

    def set_access(self, access_id, data):
        """
        Sets the description associated to an access ID.

        :param access_id: An access ID (xmpp, http, ...)
        :param data: The description associated to the given ID
        """
        with self.__lock:
            try:
                old_data = self.__accesses[access_id]
            except KeyError:
                # Unknown data
                old_data = None

            if data != old_data:
                # Update only if necessary
                self.__accesses[access_id] = data

                if not isinstance(data, RawAccess):
                    self.__callback("peer_access_set", access_id, data)

    def unset_access(self, access_id):
        """
        Removes and returns the description associated to an access ID.

        :param access_id: An access ID (xmpp, http, ...)
        :return: The associated description, or None
        """
        with self.__lock:
            try:
                data = self.__accesses.pop(access_id)
            except KeyError:
                # Unknown access
                return None
            else:
                # Notify the directory
                self.__callback("peer_access_unset", access_id, data)
                return data

# ------------------------------------------------------------------------------


class Target(object):
    """
    The description of a target, used in exceptions
    """
    def __init__(self, uid=None, group=None, uids=None, peer=None):
        """
        Sets the target definition. Only one argument should be set at once.

        :param uid: The UID of the targeted peer
        :param group: The targeted group
        :param uids: The UIDs of the targeted peers (for groups only)
        :param peer: A Peer bean
        """
        if peer is not None:
            self.__uid = peer.uid
        else:
            self.__uid = uid
        self.__group = group
        self.__uids = uids or []

    @property
    def uid(self):
        """
        The UID of the targeted peer
        """
        return self.__uid

    @property
    def group(self):
        """
        The targeted group
        """
        return self.__group

    @property
    def uids(self):
        """
        The UIDs of the targeted peers (for groups only)
        """
        return self.__uids

# ------------------------------------------------------------------------------


class RawAccess(object):
    """
    A peer access stored while no transport directory can load it
    """
    def __init__(self, access_id, raw_data):
        """
        Sets up the bean

        :param access_id: Access ID associated to the data
        :param raw_data: Raw data to store
        """
        self.__access_id = access_id
        self.__raw_data = raw_data

    @property
    def access_id(self):
        """
        The access ID associated to the data
        """
        return self.__access_id

    @property
    def data(self):
        """
        The stored data
        """
        return self.__raw_data

    def dump(self):
        """
        The dump method returns the raw data as-is
        """
        return self.__raw_data

# ------------------------------------------------------------------------------


class DelayedNotification(object):
    """
    Bean to use for delayed notification of peer registration
    """
    def __init__(self, peer, notification_method):
        """
        Sets up the bean

        :param peer: The peer being registered
        :param notification_method: The method to call to notify listeners
        (can be None to ignore notification)
        """
        self.__peer = peer
        self.__method = notification_method

    @property
    def peer(self):
        """
        The peer being registered
        """
        return self.__peer

    def notify(self):
        """
        Calls the notification method

        :return: True if the notification method has been called
        """
        if self.__method is not None:
            self.__method(self.__peer)
            return True
        return False

# ------------------------------------------------------------------------------


class Message(object):
    """
    Represents a message to be sent
    """
    def __init__(self, target_id, target_type, subject, content=None,
                 sender_uid=None, send_mode=None, replies_to=None):
        """
        Sets up members
        
        :param target_id: Target of the message (peer uid or group name)
        :param target_type: Type of the target (peer or group)
        :param subject: Subject of the message
        :param content: Content of the message (optional)
        :param sender_uid: UID of the peer sender of the message
        :param send_mode: sending mode (fire, post, send)
        :param replies_to: UID of the message that triggered this one as response (send mode).        
        """
        # set herald specification version
        self._herald_version = HERALD_SPECIFICATION_VERSION        
        
        # init headers
        self._headers = {}
        self._headers[MESSAGE_HEADER_UID] = str(uuid.uuid4()).replace('-', '').upper()
        self._headers[MESSAGE_HEADER_TIMESTAMP] = int(time.time() * 1000)        
        self._headers[MESSAGE_HEADER_SENDER_UID] = sender_uid
        self._headers[MESSAGE_HEADER_SEND_MODE] = send_mode
        self._headers[MESSAGE_HEADER_REPLIES_TO] = replies_to
        
        # init target. e.g., peer:1234567890 or group:all        
        self._target = "{0}:{1}".format(target_type, target)
        
        # init subject
        self._subject = subject
        
        # init content
        self._content = content
        
        # extra information
        self._extra = {}
            

    def __str__(self):
        """
        String representation
        """
        return "{0} ({1})".format(self._subject, self.headers[MESSAGE_UID])

    @property
    def uid(self):
        """
        Message UID
        """
        return self._headers[MESSAGE_HEADER_UID]
        
    @property
    def timestamp(self):
        """
        Time stamp of the message
        """
        return self._headers[MESSAGE_HEADER_TIMESTAMP]
    
    @property
    def sender(self):
        """
        Sender Peer UID
        """
        return self._headers[MESSAGE_HEADER_UID]
        
    @property
    def send_mode(self):
        """
        Send mode
        """
        return self._headers[MESSAGE_HEADER_SEND_MODE]    

    @property
    def replies_to(self):
        """
        UID of Peer to be replyed
        """
        return self._headers[MESSAGE_HEADER_REPLIES_TO] 
        
    @Property
    def target(self):
        """
        The target of the message (peer:<uid> or group:<name>)
        """
        return self._target

    @Property
    def target_id(self):
        """
        The id of the target of the message (<uid> or <group_name>)
        """
        return self._target.split(":")[0]
    
    @Property
    def target_type(self):
        """
        The type of the target of the message (peer or group)
        """
        return self._target.split(":")[1]
    
    @property
    def subject(self):
        """
        The subject of the message
        """
        return self._subject

    @property
    def content(self):
        """
        The content of the message
        """
        return self._content

   def get_extra(self, key):
       """
       Return extra info
       """
       return self._extra[key]

    
    @Staticmethod
    def fromJSON(json_message):
        """
        Returns a new Message from the provided json_message
        """
        # parse the provided json_message
        try:
            parsed_msg = json.loads(json_message)
        except ValueError as ex:            
            # if the provided json_message is not a valid JSON
            return None
        except TypeError as ex:
            # if json_message not string or buffer
            return None
        # check if it is a valid Herald JSON message
        if MESSAGE_HERALD_VERSION not in parsed_msg:
            # throw exception, not valid Herald message!
            return None
            
        # construct new Message object from the provided JSON object      
        msg_target = parsed_msg[MESSAGE_TARGET].split(":")[0]
        msg_target_type = parsed_msg[MESSAGE_TARGET].split(":")[1]       
        msg = Message(target=msg_target,
                      target_type=msg_target_type,
                      subject=parsed_msg[MESSAGE_SUBJECT],
                      content=parsed_msg[MESSAGE_CONTENT])
        # retrieve headers
        msg._headers[MESSAGE_HEADER_UID] = parsed_msg[MESSAGE_HEADERS][MESSAGE_HEADER_UID]
        msg._headers[MESSAGE_HEADER_TIMESTAMP] = parsed_msg[MESSAGE_HEADERS][MESSAGE_HEADER_TIMESTAMP]
        msg._headers[MESSAGE_HEADER_SENDER_UID] = parsed_msg[MESSAGE_HEADERS][MESSAGE_HEADER_SENDER_UID]
        msg._headers[MESSAGE_HEADER_SEND_MODE] = parsed_msg[MESSAGE_HEADERS][MESSAGE_HEADER_SEND_MODE]
        msg._headers[MESSAGE_HEADER_REPLIES_TO] = parsed_msg[MESSAGE_HEADERS][MESSAGE_HEADER_REPLIES_TO] 
        # extra info
        msg._extra = parsed_msg[MESSAGE_EXTRA]        
        return msg
        
    @Staticmethod    
    def fromRAW(raw_message):
        """
        Returns a new Message from the provided raw_message
        """
        pass
        
    def toJSON(self):
        """
        Returns a JSON representation of this message
        """
        result = {}
        # Herald specification version
        result[MESSAGE_HERALD_VERSION] = self._herald_version
        # all other provided headers which are not supported are not included in final JSON object
        result[MESSAGE_HEADERS] = {}
        result[MESSAGE_HEADERS][MESSAGE_HEADER_UID] = self._headers[MESSAGE_HEADER_UID]
        result[MESSAGE_HEADERS][MESSAGE_HEADER_TIMESTAMP] = self._headers[MESSAGE_HEADER_TIMESTAMP]
        result[MESSAGE_HEADERS][MESSAGE_HEADER_SENDER_UID] = self._headers[MESSAGE_HEADER_SENDER_UID]
        result[MESSAGE_HEADERS][MESSAGE_HEADER_SEND_MODE] = self._headers[MESSAGE_HEADER_SEND_MODE]
        result[MESSAGE_HEADERS][MESSAGE_HEADER_REPLIES_TO] = self._headers[MESSAGE_HEADER_REPLIES_TO]
        # basic infos
        result[MESSAGE_TARGET] = self._target
        result[MESSAGE_TARGET_TYPE] = self._target
        result[MESSAGE_SUBJECT] = self._subject
        result[MESSAGE_CONTENT] = self._content
        # all provided extra entries are included
        result[MESSAGE_EXTRA] = self._extra
        # creates the JSON object and return it
        return json.dumps(result)
        
    def toRAW(self):
        """
        Returns a RAW object of this message
        """
        pass


class MessageReceived(Message):
    """
    Represents a message received by a transport
    """
    def __init__(self, target_id, target_type, subject, content=None,
                 sender_uid=None, send_mode=None, replies_to=None,
                 uid=None, timestamp=None, access=None, replied=None):
        """
        Sets up the bean

        :param uid: Message UID
        :param timestamp: Message sending time stamp
        :param access: Access ID of the transport which received this message
        :param replied: a tag indicating if this message was replied (sent to trigger peer)
        """
        Message.__init__(self, target_id, target_type, subject, content,
                 sender_uid, send_mode, replies_to)
        # set the same UID and timestap as the original message
        self._uid = uid
        self._timestamp = timestamp
        # set headers related to the received message
        self._headers[MESSAGE_HEADER_ACCESS] = access
        self._headers[MESSAGE_HEADER_REPLIED] = replied


    def __str__(self):
        """
        String representation
        """
        return "{0} ({1}) from {2}".format(self._subject, self._uid,
                                           self._sender)

    @property
    def access(self):
        """
        Returns the access ID of the transport which received this message
        """
        return self._headers[MESSAGE_HEADER_ACCESS]

    @property
    def reply_to(self):
        """
        UID of the message this one replies to
        """
        return self._reply_to

    @property
    def sender(self):
        """
        UID of the peer that sent this message
        """
        return self._sender

    """
    @depricated!
    """
    @property
    def extra(self):
        """
        Extra information set by the transport that received this message
        """
        return self._extra
