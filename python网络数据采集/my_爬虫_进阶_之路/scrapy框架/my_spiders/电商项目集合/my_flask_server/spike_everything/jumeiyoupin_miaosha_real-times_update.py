# coding:utf-8

'''
@author = super_fazai
@File    : jumeiyoupin_miaosha_real-times_update.py
@Time    : 2018/3/18 09:42
@connect : superonesfazai@gmail.com
'''

"""
聚美优品每日10点上新商品数据实时更新
"""

import sys
sys.path.append('..')

from jumeiyoupin_parse import JuMeiYouPinParse
from my_pipeline import SqlServerMyPageInfoSaveItemPipeline

import gc
from time import sleep
import json
from pprint import pprint
import time

from settings import (
    IS_BACKGROUND_RUNNING,
    JUMEIYOUPIN_SLEEP_TIME,
    PHANTOMJS_DRIVER_PATH,
    IP_POOL_TYPE,
)

from sql_str_controller import (
    jm_delete_str_1,
    jm_select_str_1,
    jm_delete_str_2,
)

from fzutils.time_utils import get_shanghai_time
from fzutils.linux_utils import daemon_init
from fzutils.internet_utils import get_random_pc_ua
from fzutils.spider.fz_requests import Requests
from fzutils.spider.fz_phantomjs import BaseDriver
from fzutils.cp_utils import get_miaosha_begin_time_and_miaosha_end_time

class JuMeiYouPinMiaoShaRealTimeUpdate(object):
    def __init__(self):
        self._set_headers()
        self.delete_sql_str = jm_delete_str_1
        self.ip_pool_type = IP_POOL_TYPE

    def _set_headers(self):
        self.headers = {
            'Accept': 'application/json,text/javascript,text/plain,*/*;q=0.01',
            # 'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Connection': 'keep-alive',
            # 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Host': 'h5.jumei.com',
            'Referer': 'https://h5.jumei.com/',
            'Cache-Control': 'max-age=0',
            'X-Requested-With': 'XMLHttpRequest',
            'User-Agent': get_random_pc_ua(),  # 随机一个请求头
        }

    def run_forever(self):
        '''
        实时更新数据
        :return:
        '''
        tmp_sql_server = SqlServerMyPageInfoSaveItemPipeline()
        try:
            tmp_sql_server._delete_table(sql_str=jm_delete_str_2)
            result = list(tmp_sql_server._select_table(sql_str=jm_select_str_1))
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

            # 获取cookies
            my_phantomjs = BaseDriver(executable_path=PHANTOMJS_DRIVER_PATH, ip_pool_type=self.ip_pool_type)
            cookies = my_phantomjs.get_url_cookies_from_phantomjs_session(url='https://h5.jumei.com/')
            try: del my_phantomjs
            except: pass
            if cookies == '':
                print('!!! 获取cookies失败 !!!')
                return False

            print('获取cookies成功!')
            self.headers.update(Cookie=cookies)
            for item in result:     # 实时更新数据
                miaosha_end_time = json.loads(item[1]).get('miaosha_end_time')
                miaosha_end_time = int(str(time.mktime(time.strptime(miaosha_end_time, '%Y-%m-%d %H:%M:%S')))[0:10])
                # print(miaosha_end_time)

                data = {}
                # 释放内存, 在外面声明就会占用很大的, 所以此处优化内存的方法是声明后再删除释放
                jumeiyoupin_miaosha = JuMeiYouPinParse()
                if index % 50 == 0:  # 每50次重连一次，避免单次长连无响应报错
                    print('正在重置，并与数据库建立新连接中...')
                    tmp_sql_server = SqlServerMyPageInfoSaveItemPipeline()
                    print('与数据库的新连接成功建立...')

                if tmp_sql_server.is_connect_success:
                    if self.is_recent_time(miaosha_end_time) == 0:
                        tmp_sql_server._delete_table(sql_str=self.delete_sql_str, params=(item[0]))
                        print('过期的goods_id为(%s)' % item[0], ', 限时秒杀结束时间为(%s), 删除成功!' % json.loads(item[1]).get('miaosha_end_time'))

                    elif self.is_recent_time(miaosha_end_time) == 2:
                        # break       # 跳出循环
                        pass          # 此处应该是pass,而不是break，因为数据库传回的goods_id不都是按照顺序的

                    else:   # 返回1，表示在待更新区间内
                        print('------>>>| 正在更新的goods_id为(%s) | --------->>>@ 索引值为(%d)' % (item[0], index))
                        data['goods_id'] = item[0]

                        this_page_all_goods_list = self.get_one_page_all_goods_list(item[2])

                        if this_page_all_goods_list == '网络错误!':
                            print('网络错误!先跳过')
                            continue

                        elif this_page_all_goods_list == []:
                            print('#### 该page对应得到的this_page_all_goods_list为空[]!')
                            print('** 该商品已被下架限时秒杀活动, 此处将其删除')
                            tmp_sql_server._delete_table(sql_str=self.delete_sql_str, params=(item[0]))
                            print('下架的goods_id为(%s)' % item[0], ', 删除成功!')
                            pass

                        else:
                            """
                            由于不会内部提前下架，所以在售卖时间内的全部进行相关更新
                            """
                            # miaosha_goods_all_goods_id = [item_1.get('goods_id', '') for item_1 in this_page_all_goods_list]
                            #
                            # if item[0] not in miaosha_goods_all_goods_id:  # 内部已经下架的
                            #     print('该商品已被下架限时秒杀活动，此处将其删除')
                            #     tmp_sql_server._delete_table(sql_str=self.delete_sql_str, params=(item[0]))
                            #     print('下架的goods_id为(%s)' % item[0], ', 删除成功!')
                            #     pass
                            #
                            # else:  # 未下架的
                            tmp_r = jumeiyoupin_miaosha.get_goods_id_from_url(item[3])
                            jumeiyoupin_miaosha.get_goods_data(goods_id=tmp_r)
                            goods_data = jumeiyoupin_miaosha.deal_with_data()

                            if goods_data == {}:  # 返回的data为空则跳过
                                pass
                            else:
                                goods_data['goods_id'] = str(item[0])
                                goods_data['miaosha_time'] = {
                                    'miaosha_begin_time': goods_data['schedule'].get('begin_time', ''),
                                    'miaosha_end_time': goods_data['schedule'].get('end_time', ''),
                                }
                                goods_data['miaosha_begin_time'], goods_data['miaosha_end_time'] = get_miaosha_begin_time_and_miaosha_end_time(miaosha_time=goods_data['miaosha_time'])

                                # print(goods_data)
                                jumeiyoupin_miaosha.update_jumeiyoupin_xianshimiaosha_table(data=goods_data, pipeline=tmp_sql_server)
                                sleep(JUMEIYOUPIN_SLEEP_TIME)

                else:  # 表示返回的data值为空值
                    print('数据库连接失败，数据库可能关闭或者维护中')
                    pass

                index += 1
                gc.collect()
            print('全部数据更新完毕'.center(100, '#'))  # sleep(60*60)
        if get_shanghai_time().hour == 0:  # 0点以后不更新
            sleep(60 * 60 * 5.5)
        else:
            sleep(5)
        gc.collect()

    def get_one_page_all_goods_list(self, *params):
        '''
        得到一个页面地址的所有商品list
        :return: str | list 类型
        '''
        page = params[0]
        all_goods_list = []
        tmp_url = 'https://h5.jumei.com/index/ajaxDealactList?card_id=4057&page={0}&platform=wap&type=formal&page_key=1521336720'.format(str(page))
        # print('正在抓取的page为:', page, ', 接口地址为: ', tmp_url)
        body = Requests.get_url_body(url=tmp_url, headers=self.headers, ip_pool_type=self.ip_pool_type)
        # print(body)

        try:
            json_body = json.loads(body)
            # print(json_body)
        except:
            print('json.loads转换body时出错!请检查')
            json_body = {}
            return '网络错误!'

        this_page_item_list = json_body.get('item_list', [])
        if this_page_item_list == []:
            return []

        for item in this_page_item_list:
            if item.get('item_id', '') not in [item_1.get('item_id', '') for item_1 in all_goods_list]:
                item['page'] = page
                all_goods_list.append(item)

        # sleep(.5)

        all_goods_list = [{
            'goods_id': str(item.get('item_id', '')),
            'type': item.get('type', ''),
            'page': item.get('page')
        } for item in all_goods_list if item.get('item_id') is not None]

        return all_goods_list

    def is_recent_time(self, timestamp):
        '''
        判断是否在指定的日期差内
        :param timestamp: 时间戳
        :return: 0: 已过期恢复原价的 1: 待更新区间内的 2: 未来时间的
        '''
        time_1 = int(timestamp)
        time_2 = int(time.time())  # 当前的时间戳

        diff_time = time_1 - time_2
        if diff_time < -86400:  # (为了后台能同步下架)所以设置为 24个小时
            # if diff_time < 0:     # (原先的时间)结束时间 与当前时间差 <= 0
            return 0  # 已过期恢复原价的
        elif diff_time > 0:
            return 1  # 表示是昨天跟今天的也就是待更新的
        else:  # 表示过期但是处于等待的数据不进行相关先删除操作(等<=24小时时再2删除)
            return 2

    def __del__(self):
        gc.collect()

def just_fuck_run():
    while True:
        print('一次大更新即将开始'.center(30, '-'))
        tmp = JuMeiYouPinMiaoShaRealTimeUpdate()
        tmp.run_forever()
        try:
            del tmp
        except:
            pass
        gc.collect()
        print('一次大更新完毕'.center(30, '-'))
        sleep(2*60)

def main():
    '''
    这里的思想是将其转换为孤儿进程，然后在后台运行
    :return:
    '''
    print('========主函数开始========')  # 在调用daemon_init函数前是可以使用print到标准输出的，调用之后就要用把提示信息通过stdout发送到日志系统中了
    daemon_init()  # 调用之后，你的程序已经成为了一个守护进程，可以执行自己的程序入口了
    print('--->>>| 孤儿进程成功被init回收成为单独进程!')
    # time.sleep(10)  # daemon化自己的程序之后，sleep 10秒，模拟阻塞
    just_fuck_run()

if __name__ == '__main__':
    if IS_BACKGROUND_RUNNING:
        main()
    else:
        just_fuck_run()