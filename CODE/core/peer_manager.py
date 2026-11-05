class PeerManager:
    def __init__(self):
        self.peers = {}
    def add_peer(self, peer_id, ip, tcp_port):
        self.peers[peer_id] = {
            "ip": ip,
            "tcp_port": tcp_port,
        }
    def remove_peer(self, peer_id):
        if peer_id in self.peers:
            self.peers.pop(peer_id)

    def get_peer(self, peer_id):
        peer = self.peers.get(peer_id)
        if peer is None:
            print(f"Không tìm thấy peer với peer_id: {peer_id}")
            return None
        return peer
    def get_all_peers(self):
        return self.peers.copy()












