# coding:utf-8

'''
@author = super_fazai
@File    : mia_spike.py
@Time    : 2018/1/16 11:03
@connect : superonesfazai@gmail.com
'''

'''
蜜芽秒杀抓取(秒杀时间为每日的10点，15点)

19年版, 暂无秒杀板块
'''

import sys
sys.path.append('..')

import re
import time
from pprint import pprint
import gc
from time import sleep

from settings import MIA_BASE_NUMBER, MIA_MAX_NUMBER, MIA_SPIKE_SLEEP_TIME
from mia_parse import MiaParse
from my_pipeline import SqlServerMyPageInfoSaveItemPipeline

from settings import (
    IS_BACKGROUND_RUNNING,
    IP_POOL_TYPE,)

from sql_str_controller import mia_select_str_4

from fzutils.time_utils import (
    timestamp_to_regulartime,
)
from fzutils.linux_utils import daemon_init
from fzutils.internet_utils import get_random_pc_ua
from fzutils.spider.fz_requests import Requests
from fzutils.cp_utils import get_miaosha_begin_time_and_miaosha_end_time
from fzutils.common_utils import json_2_dict

class MiaSpike(object):
    def __init__(self):
        self._set_headers()
        self.ip_pool_type = IP_POOL_TYPE

    def _set_headers(self):
        self.headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            # 'Accept-Encoding:': 'gzip',
            'Accept-Language': 'zh-CN,zh;q=0.8',
            'Cache-Control': 'max-age=0',
            'Connection': 'keep-alive',
            'Host': 'm.mia.com',
            'User-Agent': get_random_pc_ua(),  # 随机一个请求头
        }

    def _get_db_goods_id_list(self) -> (list, None):
        my_pipeline = SqlServerMyPageInfoSaveItemPipeline()
        try:
            _ = list(my_pipeline._select_table(sql_str=mia_select_str_4))
            db_goods_id_list = [item[0] for item in _]
        except Exception:
            return None

        return db_goods_id_list

    def get_spike_hour_goods_info(self):
        '''
        模拟构造得到data的url，得到近期所有的限时秒杀商品信息
        :return:
        '''
        mia_base_number = MIA_BASE_NUMBER
        self.db_goods_id_list = self._get_db_goods_id_list()
        assert self.db_goods_id_list is not None, 'self.db_goods_id_list为空值!'
        while mia_base_number < MIA_MAX_NUMBER:
            tmp_url = 'https://m.mia.com/instant/seckill/seckillPromotionItem/' + str(mia_base_number)
            body = Requests.get_url_body(url=tmp_url, headers=self.headers, had_referer=True, ip_pool_type=self.ip_pool_type)
            # print(body)
            if body == '' or body == '[]':
                print('mia_base_number为: ', mia_base_number)
                print('获取到的body为空值! 此处跳过')
                mia_base_number += 1
                continue

            else:
                tmp_data = json_2_dict(body, default_res={})
                tmp_hour = tmp_data.get('p_info', {}).get('start_time', '')[11:13]
                if tmp_hour == '22':    # 过滤掉秒杀时间为22点的
                    print('--- 销售时间为22点，不抓取!')
                    pass
                else:
                    print(tmp_data)
                    print('mia_base_number为: ', mia_base_number)
                    pid = mia_base_number
                    begin_time = tmp_data.get('p_info', {}).get('start_time', '')
                    end_time = tmp_data.get('p_info', {}).get('end_time', '')
                    item_list = tmp_data.get('item_list', [])

                    self.deal_with_data(pid, begin_time, end_time, item_list)
                    sleep(5)

            mia_base_number += 1

    def deal_with_data(self, *param):
        '''
        处理并存储相关秒杀商品的数据
        :param param: 相关参数
        :return:
        '''
        pid = param[0]
        begin_time = int(time.mktime(time.strptime(param[1], '%Y/%m/%d %H:%M:%S')))     # 把str字符串类型转换为时间戳的形式
        end_time = int(time.mktime(time.strptime(param[2], '%Y/%m/%d %H:%M:%S')))
        item_list = param[3]

        mia = MiaParse()
        my_pipeline = SqlServerMyPageInfoSaveItemPipeline()
        if my_pipeline.is_connect_success:
            for item in item_list:
                if item.get('item_id', '') in self.db_goods_id_list:
                    print('该goods_id已经存在于数据库中, 此处跳过')
                    pass
                else:
                    goods_id = str(item.get('item_id', ''))
                    tmp_url = 'https://www.mia.com/item-' + str(goods_id) + '.html'

                    mia.get_goods_data(goods_id=str(goods_id))
                    goods_data = mia.deal_with_data()
                    if goods_data == {}:  # 返回的data为空则跳过
                        pass

                    else:  # 否则就解析并且插入
                        goods_url = goods_data['goods_url']
                        if re.compile(r'://m.miyabaobei.hk/').findall(goods_url) != '':
                            goods_url = 'https://www.miyabaobei.hk/item-' + str(goods_id) + '.html'
                        else:
                            goods_url = 'https://www.mia.com/item-' + str(goods_id) + '.html'
                        goods_data['goods_url'] = goods_url
                        goods_data['goods_id'] = str(goods_id)
                        goods_data['price'] = item.get('active_price')
                        goods_data['taobao_price'] = item.get('active_price')       # 秒杀最低价
                        goods_data['sub_title'] = item.get('short_info', '')
                        goods_data['miaosha_time'] = {
                            'miaosha_begin_time': timestamp_to_regulartime(begin_time),
                            'miaosha_end_time': timestamp_to_regulartime(end_time),
                        }
                        goods_data['miaosha_begin_time'], goods_data['miaosha_end_time'] = get_miaosha_begin_time_and_miaosha_end_time(miaosha_time=goods_data['miaosha_time'])
                        goods_data['pid'] = str(pid)

                        # pprint(goods_data)
                        # print(goods_data)
                        res = mia.insert_into_mia_xianshimiaosha_table(data=goods_data, pipeline=my_pipeline)
                        if res:
                            if goods_id not in self.db_goods_id_list:
                                self.db_goods_id_list.append(goods_id)

                        sleep(MIA_SPIKE_SLEEP_TIME)  # 放慢速度
        else:
            print('数据库连接失败，此处跳过!')
            pass

        try:
            del mia
        except:
            pass
        gc.collect()

    def __del__(self):
        gc.collect()

def just_fuck_run():
    while True:
        print('一次大抓取即将开始'.center(30, '-'))
        mia_spike = MiaSpike()
        mia_spike.get_spike_hour_goods_info()
        gc.collect()
        sleep(1 * 60)
        print('一次大抓取完毕, 即将重新开始'.center(30, '-'))

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