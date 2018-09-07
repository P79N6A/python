# coding:utf-8

'''
@author = super_fazai
@File    : tmall_migrate.py
@Time    : 2018/3/15 09:42
@connect : superonesfazai@gmail.com
'''

import sys
sys.path.append('..')

from tmall_parse import TmallParse
from my_pipeline import SqlServerMyPageInfoSaveItemPipeline
import gc
from time import sleep
from settings import IS_BACKGROUND_RUNNING

from sql_str_controller import (
    tm_select_str_1,
    tm_select_str_2,
)

from fzutils.time_utils import get_shanghai_time
from fzutils.linux_utils import daemon_init

def run_forever():
    while True:
        #### 实时更新数据
        tmp_sql_server = SqlServerMyPageInfoSaveItemPipeline()
        try:
            result = list(tmp_sql_server._select_table(sql_str=tm_select_str_1))
            result_2 = list(tmp_sql_server._select_table(sql_str=tm_select_str_2, params=None))
        except TypeError:
            print('TypeError错误, 原因数据库连接失败...(可能维护中)')
            result = None
            result_2 = []
        if result is None:
            pass
        else:
            print('------>>> 下面是数据库返回的所有符合条件的goods_id <<<------')
            print(result_2)
            print('--------------------------------------------------------')

            print('即将开始实时更新数据, 请耐心等待...'.center(100, '#'))
            index = 1
            # 释放内存,在外面声明就会占用很大的，所以此处优化内存的方法是声明后再删除释放
            tmall = TmallParse()
            for item in result_2:  # 实时更新数据
                if index % 5 == 0:
                    tmall = TmallParse()
                    gc.collect()

                if index % 50 == 0:    # 每50次重连一次，避免单次长连无响应报错
                    print('正在重置，并与数据库建立新连接中...')
                    # try:
                    #     del tmp_sql_server
                    # except:
                    #     pass
                    # gc.collect()
                    tmp_sql_server = SqlServerMyPageInfoSaveItemPipeline()
                    print('与数据库的新连接成功建立...')

                if tmp_sql_server.is_connect_success:
                    goods_id = tmall.get_goods_id_from_url(item[0])
                    if goods_id == []:
                        print('@@@ 原地址为: ', item[0])
                        continue
                    else:
                        print('------>>>| 正在更新的goods_id为(%s) | --------->>>@ 索引值为(%d)' % (goods_id[1], index))
                        data = tmall.get_goods_data(goods_id=goods_id)
                        if isinstance(data, int):
                            continue

                        if data.get('is_delete') == 1:
                            data['goods_id'] = goods_id[1]

                            # 改进判断，根据传入数据判断是天猫，还是天猫超市，还是天猫国际
                            #####################################################
                            if goods_id[0] == 0:  # [0, '1111']
                                wait_to_deal_with_url = 'https://detail.tmall.com/item.htm?id=' + goods_id[1]  # 构造成标准干净的天猫商品地址
                            elif goods_id[0] == 1:  # [1, '1111']
                                wait_to_deal_with_url = 'https://chaoshi.detail.tmall.com/item.htm?id=' + goods_id[1]
                            elif goods_id[0] == 2:  # [2, '1111', 'https://xxxxx']
                                wait_to_deal_with_url = str(goods_id[2]) + '?id=' + goods_id[1]
                            else:
                                continue
                            data['goods_url'] = wait_to_deal_with_url
                            data['username'] = '18698570079'
                            data['main_goods_id'] = item[1]

                            # print('------>>>| 爬取到的数据为: ', data)
                            result = tmall.old_tmall_goods_insert_into_new_table(data, pipeline=tmp_sql_server)
                            if result is False:
                                print('出错商品的地址为: ', item[0])
                            else:
                                pass
                            index += 1
                            gc.collect()
                            sleep(1.2)
                            continue
                        else:
                            pass

                        data = tmall.deal_with_data()
                        if data != {}:
                            data['goods_id'] = goods_id[1]

                            # 改进判断，根据传入数据判断是天猫，还是天猫超市，还是天猫国际
                            #####################################################
                            if goods_id[0] == 0:  # [0, '1111']
                                wait_to_deal_with_url = 'https://detail.tmall.com/item.htm?id=' + goods_id[1]  # 构造成标准干净的天猫商品地址
                            elif goods_id[0] == 1:  # [1, '1111']
                                wait_to_deal_with_url = 'https://chaoshi.detail.tmall.com/item.htm?id=' + goods_id[1]
                            elif goods_id[0] == 2:  # [2, '1111', 'https://xxxxx']
                                wait_to_deal_with_url = str(goods_id[2]) + goods_id[1]
                            else:
                                continue
                            data['goods_url'] = wait_to_deal_with_url
                            data['username'] = '18698570079'
                            data['main_goods_id'] = item[1]

                            # print('------>>>| 爬取到的数据为: ', data)
                            tmall.old_tmall_goods_insert_into_new_table(data, pipeline=tmp_sql_server)
                        else:  # 表示返回的data值为空值
                            pass
                else:  # 表示返回的data值为空值
                    print('数据库连接失败，数据库可能关闭或者维护中')
                    pass
                index += 1
                gc.collect()
                sleep(2)
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