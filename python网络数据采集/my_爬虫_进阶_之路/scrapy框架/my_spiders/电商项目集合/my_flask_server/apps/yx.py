# coding:utf-8

'''
@author = super_fazai
@File    : yx.py
@Time    : 2017/8/11 13:54
@connect : superonesfazai@gmail.com
'''

"""
网易严选
"""

import re
import gc
from json import dumps
import sys

from .reuse import (
    add_base_info_2_processed_data,
)

sys.path.append('..')
from settings import DEFAULT_USERNAME
from yanxuan_parse import YanXuanParse

def _get_yanxuan_wait_to_save_data_goods_id_list(data, my_lg):
    '''
    获取严选待存取的goods_id的list
    :param data:
    :return:
    '''
    wait_to_save_data_url_list = data

    tmp_wait_to_save_data_goods_id_list = []
    for item in wait_to_save_data_url_list:
        if item == '':  # 除去传过来是空值
            pass
        else:
            is_kaola_url = re.compile(r'you.163.com/item/detail.*?').findall(item)
            if is_kaola_url != []:
                try:
                    goods_id = re.compile(r'id=(\d+)').findall(item)[0]
                except IndexError:
                    continue
                my_lg.info('------>>>| 得到的严选商品的goods_id为: {0}'.format(goods_id))
                tmp_wait_to_save_data_goods_id_list.append(goods_id)
            else:
                my_lg.info('网易严选商品url错误, 非正规的url, 请参照格式(https://you.163.com/item/detail)开头的...')
                pass

    return tmp_wait_to_save_data_goods_id_list

def _get_db_yanxuan_insert_params(item):
    '''
    得到db待插入的严选数据
    :param item:
    :return:
    '''
    params = (
        item['goods_id'],
        item['goods_url'],
        item['username'],
        item['create_time'],
        item['modify_time'],
        item['shop_name'],
        item['account'],
        item['title'],
        item['sub_title'],
        item['link_name'],
        item['price'],
        item['taobao_price'],
        dumps(item['price_info'], ensure_ascii=False),
        dumps(item['detail_name_list'], ensure_ascii=False),  # 把list转换为json才能正常插入数据(并设置ensure_ascii=False)
        dumps(item['price_info_list'], ensure_ascii=False),
        dumps(item['all_img_url'], ensure_ascii=False),
        dumps(item['p_info'], ensure_ascii=False),  # 存入到PropertyInfo
        item['div_desc'],  # 存入到DetailInfo
        item['all_sell_count'],
        dumps(item['schedule'], ensure_ascii=False),

        item['site_id'],
        item['is_delete'],
        item['parent_dir'],
    )

    return params

def get_one_yanxuan_data(**kwargs):
    '''
    抓取一个严选商品地址的数据
    :param kwargs:
    :return:
    '''
    username = kwargs.get('username', DEFAULT_USERNAME)
    wait_to_deal_with_url = kwargs.get('wait_to_deal_with_url', '')
    my_lg = kwargs.get('my_lg')

    yanxuan = YanXuanParse(logger=my_lg)
    goods_id = yanxuan.get_goods_id_from_url(wait_to_deal_with_url)  # 获取goods_id, 这里返回的是一个list
    if goods_id == '':  # 如果得不到goods_id, 则return error
        my_lg.info('获取到的goods_id为空!')
        try:
            del yanxuan  # 每次都回收一下
        except Exception:
            pass
        gc.collect()
        return {'goods_id': ''}  # 错误1: goods_id为空值

    tmp_result = yanxuan._get_goods_data(goods_id=goods_id)
    data = yanxuan._deal_with_data()  # 如果成功获取的话, 返回的是一个data的dict对象
    if data == {} or tmp_result == {}:
        my_lg.error('获取到的data为空!出错地址: {0}'.format(wait_to_deal_with_url))
        try:
            del yanxuan
        except:
            pass
        gc.collect()
        return {'goods_id': goods_id, 'msg': 'data为空!'}  # 错误2: 抓取失败

    wait_to_save_data = add_base_info_2_processed_data(
        data=data,
        spider_url=wait_to_deal_with_url,
        username=username,
        goods_id=goods_id
    )
    try:
        del yanxuan
    except:
        pass

    return wait_to_save_data
