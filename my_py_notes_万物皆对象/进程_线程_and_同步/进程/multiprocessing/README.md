# multiprocessing

如果你打算编写多进程的服务程序, Unix/Linux⽆疑是正确的选择.

由于Windows没有fork调⽤, 难道在Windows上⽆法⽤Python编写多进程的程序？

由于Python是跨平台的, ⾃然也应该提供⼀个跨平台的多进程⽀持.

multiprocessing模块就是跨平台版本的多进程模块。

multiprocessing模块提供了⼀个Process类来代表⼀个进程对象

## Process
### Process语法结构如下:
Process([group [, target [, name [, args [, kwargs]]]]])
- target： 表示这个进程实例所调⽤对象；
- args：   表示调⽤对象的位置参数元组；
- kwargs： 表示调⽤对象的关键字参数字典；
- name：   为当前进程实例的别名；
- group：  ⼤多数情况下⽤不到；

### Process类常⽤⽅法：
- is_alive()： 判断进程实例是否还在执⾏；
- join([timeout])： 是否等待进程实例执⾏结束， 或等待多少秒；
- start()： 启动进程实例（ 创建⼦进程） ；
- run()： 如果没有给定target参数, 对这个对象调⽤start()⽅法时, 就将执⾏对象中的run()⽅法；
- terminate()： 不管任务是否完成， ⽴即终⽌；
### Process类常⽤属性：
- name： 当前进程实例别名， 默认为Process-N， N为从1开始递增的整数；
- pid： 当前进程实例的PID值；