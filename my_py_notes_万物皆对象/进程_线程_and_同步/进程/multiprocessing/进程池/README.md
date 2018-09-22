# 进程池

## 当需要创建的⼦进程数量不多时
可以直接利⽤multiprocessing中的Process动态成⽣多个进程

## 但如果是上百甚⾄上千个⽬标
⼿动的去创建进程的⼯作量巨⼤, 此时就可以⽤到multiprocessing模块提供的Pool⽅法

初始化Pool时, 可以指定⼀个最⼤进程数

当有新的请求提交到Pool中时，
1. 如果池还没有满, 那么就会创建⼀个新的进程⽤来执⾏该请求;
2. 但如果池中的进程数已经达到指定的最⼤值, 那么该请求就会等待, 直到池中有进程结束, 才会创建新的进程来执⾏

- multiprocessing.Pool常⽤函数解析：
    - apply_async(func[, args[, kwds]]): 使⽤⾮阻塞⽅式调⽤func(并⾏执⾏， 堵塞⽅式必须等待上⼀个进程退出才能执⾏下⼀个进程, args为传递给func的参数列表， kwds为传递给func的关键字参数列表；
    - apply(func[, args[, kwds]]): 使⽤阻塞⽅式调⽤func
    - close(): 关闭Pool， 使其不再接受新的任务；
    - terminate(): 不管任务是否完成， ⽴即终⽌；
    - join(): 主进程阻塞， 等待⼦进程的退出， 必须在close或terminate之后使⽤；