'''
Created on Aug 20, 2013

@author: amr
'''
import redis


REDIS_POOL = redis.ConnectionPool(host='localhost', port=6379, db=0)