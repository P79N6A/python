# coding:utf-8

'''
@author = super_fazai
@File    : youpin_real-times_update.py
@Time    : 2018/8/16 09:24
@connect : superonesfazai@gmail.com
'''

import sys
sys.path.append('..')

from my_pipeline import SqlServerMyPageInfoSaveItemPipeline
from youpin_parse import YouPinParse

import gc
from time import sleep
from logging import (
    INFO,
    ERROR)
from settings import (
    IS_BACKGROUND_RUNNING,
    MY_SPIDER_LOGS_PATH,
    TMALL_REAL_TIMES_SLEEP_TIME,)

from sql_str_controller import (
    yp_select_str_1,
    yp_update_str_2,)
from multiplex_code import get_sku_info_trans_record

from fzutils.log_utils import set_logger
from fzutils.time_utils import (
    get_shanghai_time,
)
from fzutils.linux_utils import daemon_init
from fzutils.cp_utils import (
    _get_price_change_info,
    get_shelf_time_and_delete_time,
    format_price_info_list,
)
from fzutils.common_utils import json_2_dict

def run_forever():
    while True:
        # ** 不能写成全局变量并放在循环中, 否则会一直记录到同一文件中
        my_lg = set_logger(
            log_file_name=MY_SPIDER_LOGS_PATH + '/小米有品/实时更新/' + str(get_shanghai_time())[0:10] + '.txt',
            console_log_level=INFO,
            file_log_level=ERROR
        )

        #### 实时更新数据
        tmp_sql_server = SqlServerMyPageInfoSaveItemPipeline()
        try:
            result = list(tmp_sql_server._select_table(sql_str=yp_select_str_1))
        except TypeError:
            my_lg.error('TypeError错误, 原因数据库连接失败...(可能维护中)')
            result = None
        if result is None:
            pass
        else:
            my_lg.info('------>>> 下面是数据库返回的所有符合条件的goods_id <<<------')
            my_lg.info(str(result))
            my_lg.info('--------------------------------------------------------')
            my_lg.info('总计待更新个数: {0}'.format(len(result)))

            my_lg.info('即将开始实时更新数据, 请耐心等待...'.center(100, '#'))
            index = 1

            yp = YouPinParse(logger=my_lg)
            for item in result:
                if index % 5 == 0:
                    try:
                        del yp
                    except: pass
                    yp = YouPinParse(logger=my_lg)
                    gc.collect()

                if index % 10 == 0:  # 每10次重连一次，避免单次长连无响应报错
                    my_lg.info('正在重置，并与数据库建立新连接中...')
                    tmp_sql_server = SqlServerMyPageInfoSaveItemPipeline()
                    my_lg.info('与数据库的新连接成功建立...')

                if tmp_sql_server.is_connect_success:
                    my_lg.info('------>>>| 正在更新的goods_id为(%s) | --------->>>@ 索引值为(%s)' % (str(item[1]), str(index)))
                    yp._get_target_data(goods_id=item[1])

                    data = yp._handle_target_data()
                    if data != {}:
                        data['goods_id'] = item[1]
                        data['shelf_time'], data['delete_time'] = get_shelf_time_and_delete_time(
                            tmp_data=data,
                            is_delete=item[2],
                            shelf_time=item[5],
                            delete_time=item[6])
                        if data.get('is_delete') == 1:  # 单独处理下架商品
                            my_lg.info('@@@ 该商品已下架...')
                            tmp_sql_server._update_table_2(sql_str=yp_update_str_2, params=(item[1],), logger=my_lg)
                            sleep(TMALL_REAL_TIMES_SLEEP_TIME)
                            continue
                        else:
                            data['_is_price_change'], data['_price_change_info'] = _get_price_change_info(
                                old_price=item[3],
                                old_taobao_price=item[4],
                                new_price=data['price'],
                                new_taobao_price=data['taobao_price']
                            )
                            try:
                                old_sku_info = format_price_info_list(price_info_list=json_2_dict(item[7]), site_id=31)
                            except AttributeError:  # 处理已被格式化过的
                                old_sku_info = item[7]
                            data['_is_price_change'], data['sku_info_trans_time'] = get_sku_info_trans_record(
                                old_sku_info=old_sku_info,
                                new_sku_info=format_price_info_list(data['price_info_list'], site_id=31),
                                is_price_change=item[8] if item[8] is not None else 0
                            )

                        yp._to_right_and_update_data(data, pipeline=tmp_sql_server)
                    else:  # 表示返回的data值为空值
                        my_lg.info('------>>>| 休眠8s中...')
                        sleep(8)

                else:  # 表示返回的data值为空值
                    my_lg.error('数据库连接失败，数据库可能关闭或者维护中')
                    sleep(5)
                    pass
                index += 1
                gc.collect()
                sleep(TMALL_REAL_TIMES_SLEEP_TIME)

            my_lg.info('全部数据更新完毕'.center(100, '#'))  # sleep(60*60)

        if get_shanghai_time().hour == 0:  # 0点以后不更新
            sleep(60 * 60 * 5.5)
        else:
            sleep(5 * 60)
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