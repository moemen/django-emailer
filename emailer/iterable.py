'''
Created on Aug 20, 2013

@author: amr
'''
import redis
from settings import REDIS_POOL


class RedisList(list):
    def __init__(self, redis_key, *args, **kwargs):
        super(RedisList, self).__init__(*args, **kwargs)
        self.r = redis.Redis(connection_pool=REDIS_POOL)
        if self.r.exists(redis_key):
            self.redis_key = redis_key
        else:
            raise Exception('key does not exist')

    def __getitem__(self, index):
        return self.r.lindex(self.redis_key, index)

    def pop(self):
        return self.r.rpop(self.redis_key)
