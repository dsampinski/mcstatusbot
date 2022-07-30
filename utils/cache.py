import os

class cache:
    def __init__(self):
        self.update = {}
        
        if not os.path.exists('./cache/update/'):
            if not os.path.exists('./cache/'):
                os.mkdir('./cache/')
            os.mkdir('./cache/update/')