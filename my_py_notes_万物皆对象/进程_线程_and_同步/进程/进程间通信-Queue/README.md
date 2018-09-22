# Queue的使用
可以使用multiprocessing模块的Queue实现多进程之间的数据传递

Queue本身就是一个消息队列程序

## 说明:
初始化Queue()对象时(eg. q=Queue()), 若括号中没有指定最⼤可接收的消息数量, 或数量为负值, 那么就代表可接受的消息数量没有上限(直到内存的尽头)

- Queue.qsize()： 返回当前队列包含的消息数量；
- Queue.empty()： 如果队列为空， 返回True， 反之False ；
- Queue.full()：  如果队列满了， 返回True,反之False；

### 默认get读取数据的方式也是阻塞的, 表示队列已空, 则需等待队列有数据的时候, 才能获取到数据
- Queue.get([block[, timeout]])： 获取队列中的⼀条消息, 然后将其从列队中移除, block默认值为True；
    1. 如果block使⽤默认值, 且没有设置timeout(单位秒), 消息列队如果为空, 此时程序将被阻塞(停在读取状态), 直到从消息列队读到消息为⽌, 如果设置了timeout, 则会等待timeout秒, 若还没读取到任何消息, 则抛出"Queue.Empty"异常;
    2. 如果block值为False, 消息列队如果为空, 则会⽴刻抛出"Queue.Empty"异常;
- Queue.get_nowait(): 相当Queue.get(False);

### 默认put添加数据的方式是阻塞的, 表示如果添加数据已满, 则要等待队列有空闲位置的时候, 数据才能添加进去
- Queue.put(item,[block[, timeout]]): 将item消息写⼊队列, block默认值为True；
    1. 如果block使⽤默认值， 且没有设置timeout(单位秒), 消息列队如果已经没有空间可写⼊， 此时程序将被阻塞（ 停在写⼊状态） ， 直到从消息列队腾出空间为⽌， 如果设置了timeout， 则会等待timeout秒， 若还没空间， 则抛出"Queue.Full"异常；
    2. 如果block值为False， 消息列队如果没有空间可写⼊， 则会⽴刻抛出"Queue.Full"异常；
- Queue.put_nowait(item)： 相当Queue.put(item, False)；

### 注意queue的put, get方法都是操作系统给实现的, 里面的方法都是对queue队列的引用
### 都是对queue消息队列对象的操作