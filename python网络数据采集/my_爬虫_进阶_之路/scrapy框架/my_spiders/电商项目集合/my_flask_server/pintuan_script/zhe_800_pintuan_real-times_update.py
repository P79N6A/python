# coding:utf-8

'''
@author = super_fazai
@File    : zhe_800_pintuan_real-times_update.py
@Time    : 2017/12/19 11:10
@connect : superonesfazai@gmail.com
'''

import sys
sys.path.append('..')

from zhe_800_pintuan_parse import Zhe800PintuanParse
from my_pipeline import SqlServerMyPageInfoSaveItemPipeline

import gc
from time import sleep
import re
from settings import (
    IS_BACKGROUND_RUNNING,
    ZHE_800_PINTUAN_SLEEP_TIME,)

from sql_str_controller import (
    z8_delete_str_1,
    z8_select_str_2,
    z8_delete_str_2,)

from fzutils.time_utils import get_shanghai_time
from fzutils.linux_utils import daemon_init

def run_forever():
    while True:
        #### 实时更新数据
        tmp_sql_server = SqlServerMyPageInfoSaveItemPipeline()
        try:
            tmp_sql_server._delete_table(sql_str=z8_delete_str_1)
            result = list(tmp_sql_server._select_table(sql_str=z8_select_str_2))
        except TypeError:
            print('TypeError错误, 原因数据库连接失败...(可能维护中)')
            result = None
        if result is None:
            pass
        else:
            print('------>>> 下面是数据库返回的所有符合条件的goods_id <<<------')
            print(result)
            print('--------------------------------------------------------')

            print('即将开始实时更新数据, 请耐心等待...'.center(100, '#'))
            index = 1
            for item in result:  # 实时更新数据
                # 释放内存,在外面声明就会占用很大的，所以此处优化内存的方法是声明后再删除释放
                zhe_800_pintuan = Zhe800PintuanParse()
                if index % 50 == 0:    # 每50次重连一次，避免单次长连无响应报错
                    print('正在重置，并与数据库建立新连接中...')
                    tmp_sql_server = SqlServerMyPageInfoSaveItemPipeline()
                    print('与数据库的新连接成功建立...')

                if index % 300 == 0:    # 每更新300个，休眠3分钟
                    sleep_time = 3 * 60
                    sleep(sleep_time)
                    print('休眠{}s中...'.format(sleep_time))

                if tmp_sql_server.is_connect_success:
                    tmp_tmp = zhe_800_pintuan.get_goods_data(goods_id=item[0])
                    # 不用这个了因为会影响到正常情况的商品
                    try:        # 单独处理商品页面不存在的情况
                        if isinstance(tmp_tmp, str) and re.compile(r'^ze').findall(tmp_tmp) != []:
                            print('@@ 该商品的页面已经不存在!此处将其删除!')
                            tmp_sql_server._delete_table(sql_str=z8_delete_str_2, params=(item[0],))
                            sleep(ZHE_800_PINTUAN_SLEEP_TIME)
                            continue
                        else:
                            pass
                    except:
                        pass

                    data = zhe_800_pintuan.deal_with_data()
                    if data != {}:
                        data['goods_id'] = item[0]

                        if item[1] == 1:
                            tmp_sql_server._delete_table(sql_str=z8_delete_str_2, params=(item[0],))
                            print('该goods_id[{0}]已过期，删除成功!'.format(item[0]))
                        else:
                            print('------>>>| 正在更新的goods_id为(%s) | --------->>>@ 索引值为(%d)' % (item[0], index))
                            zhe_800_pintuan.to_right_and_update_data(data=data, pipeline=tmp_sql_server)
                    else:  # 表示返回的data值为空值
                        pass

                else:  # 表示返回的data值为空值
                    print('数据库连接失败，数据库可能关闭或者维护中')
                    pass
                index += 1
                try:
                    del zhe_800_pintuan
                except:
                    pass
                gc.collect()
                sleep(ZHE_800_PINTUAN_SLEEP_TIME)
            print('全部数据更新完毕'.center(100, '#'))  # sleep(60*60)
        if get_shanghai_time().hour == 0:  # 0点以后不更新
            sleep(60 * 60 * 5.5)
        else:
            sleep(5)
        gc.collect()

def main():
    '''
    这里的思想是将其转换为孤儿进程，然后在后台运行
    :return:
    '''
    print('========主函数开始========')  # 在调用daemon_init函数前是可以使用print到标准输出的，调用之后就要用把提示信息通过stdout发送到日志系统中了
    daemon_init()  # 调用之后，你的程序已经成为了一个守护进程，可以执行自己的程序入口了
    print('--->>>| 孤儿进程成功被init回收成为单独进程!')
    # time.sleep(10)  # daemon化自己的程序之后，sleep 10秒，模拟阻塞
    run_forever()

if __name__ == '__main__':
    if IS_BACKGROUND_RUNNING:
        main()
    else:
        run_forever()
