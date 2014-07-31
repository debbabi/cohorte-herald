#!/usr/bin/python
# -- Content-Encoding: UTF-8 --
"""
Herald Core directory
"""

# Herald
import herald
import herald.beans as beans

# Pelix
from pelix.ipopo.decorators import ComponentFactory, RequiresMap, Provides, \
    Validate, Invalidate, Instantiate
import pelix.constants

# Standard library
import logging

# ------------------------------------------------------------------------------

_logger = logging.getLogger(__name__)

# ------------------------------------------------------------------------------


@ComponentFactory("herald-directory-factory")
@Provides(herald.SERVICE_DIRECTORY)
@RequiresMap('_directories', herald.SERVICE_TRANSPORT_DIRECTORY,
             herald.PROP_ACCESS_ID, False, False, True)
@Instantiate("herald-directory")
class HeraldDirectory(object):
    """
    Core Directory for Herald
    """
    def __init__(self):
        """
        Sets up the transport
        """
        # Transport-specific directories
        self._directories = {}

        # Local bean description
        self._local_uid = None
        self._local = None

        # UID -> Peer bean
        self._peers = {}

        # Group name -> Peer UIDs
        self._groups = {}

    @Validate
    def _validate(self, context):
        """
        Component validated
        """
        # Clean up remaining data (if any)
        self._peers.clear()
        self._groups.clear()

        # Setup the local peer description
        self._local_uid = context.get_property(herald.FWPROP_PEER_UID) \
            or context.get_property(pelix.constants.FRAMEWORK_UID)
        self._local = beans.Peer(self._local_uid, self)

        # Setup node and name information
        self._local.name = context.get_property(herald.FWPROP_PEER_NAME) \
            or self._local_uid
        self._local.node_uid = context.get_property(herald.FWPROP_NODE_UID) \
            or self._local_uid
        self._local.node_name = context.get_property(herald.FWPROP_NODE_NAME) \
            or self._local.node_uid

    @Invalidate
    def _invalidate(self, context):
        """
        Component invalidated
        """
        # Clean all up
        self._peers.clear()
        self._groups.clear()
        self._local = None

    @property
    def local_uid(self):
        """
        Returns the local peer UID
        """
        return self._local_uid

    def get_peer(self, uid):
        """
        Retrieves the peer with the given UID

        :param uid: The UID of a peer
        :return: A Peer bean
        :raise KeyError: Unknown peer
        """
        return self._peers[uid]

    def get_local_peer(self):
        """
        Returns the description of the local peer

        :return: The description of the local peer
        """
        return self._local

    def get_peers(self):
        """
        Returns the list of all known peers
        """
        return tuple(self._peers.values())

    def peer_access_set(self, peer, access_id, data):
        """
        A new peer access is available. Called by a Peer bean.

        :param peer: The modified Peer bean
        :param access_id: ID of the access
        :param data: Information of the peer access
        """
        try:
            # Get the handling directory
            directory = self._directories[access_id]
        except KeyError:
            # No handler for this directory
            pass
        else:
            try:
                # Notify it
                directory.peer_access_set(peer, data)
            except Exception as ex:
                _logger.exception("Error notifying a transport directory: %s",
                                  ex)

    def peer_access_unset(self, peer, access_id, data):
        """
        A peer access has been removed. Called by  a Peer bean.

        :param peer: The modified Peer bean
        :param access_id: ID of the removed access
        :param data: Previous information of the peer access
        """
        try:
            # Get the handling directory
            directory = self._directories[access_id]
        except KeyError:
            # No handler for this directory
            pass
        else:
            try:
                # Notify it
                directory.peer_access_unset(peer, data)
            except Exception as ex:
                _logger.exception("Error notifying a transport directory: %s",
                                  ex)

    def dump(self):
        """
        Dumps the content of the local directory in a dictionary

        :return: A UID -> description dictionary
        """
        return {peer.uid: peer.dump() for peer in self._peers.values()}

    def load(self, dump):
        """
        Loads the content of a dump

        :param dump: The result of a call to dump()
        """
        for uid, description in dump.items():
            if uid not in self._peers:
                # Do not reload already known peer
                self.register(description)

    def register(self, description):
        """
        Registers a peer

        :param description: Description of the peer, in the format of dump()
        """
        uid = description['uid']
        if uid == self._local_uid or uid in self._peers:
            # Local/Already known peer: ignore
            return

        # Make a new bean
        peer = beans.Peer(uid, self)

        # Setup writable properties
        for name in ('name', 'node_uid', 'node_name', 'groups'):
            setattr(peer, name, description[name])

        # Accesses
        for access_id, data in description['accesses'].items():
            try:
                data = self._directories[access_id].load_access(data)
            except KeyError:
                # Access not available for parsing
                pass

            # Store the parsed data, or keep it as is
            peer.set_access(access_id, data)

        # Store the peer
        self._peers[uid] = peer
        _logger.info("Registered peer: %s", peer)

    def unregister(self, uid):
        """
        Unregisters a peer from the directory

        :param uid: UID of the peer
        :return: The Peer bean if it was known, else None
        """
        return self._peers.pop(uid, None)
