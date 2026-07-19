class BrowserManager:

    def __init__(self):

        self.started = False

    async def start(self):

        self.started = False

    async def stop(self):

        pass


browser = BrowserManager()