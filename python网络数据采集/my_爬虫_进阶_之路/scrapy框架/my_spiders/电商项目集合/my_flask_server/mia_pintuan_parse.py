# coding:utf-8

'''
@author = super_fazai
@File    : mia_pintuan_parse.py
@Time    : 2018/1/20 11:33
@connect : superonesfazai@gmail.com
'''

'''
蜜芽拼团页面解析系统
'''

import time
from pprint import pprint
from time import sleep
import gc
from scrapy import Selector
from json import dumps

from mia_parse import MiaParse
from my_pipeline import SqlServerMyPageInfoSaveItemPipeline

from sql_str_controller import (
    mia_update_str_2,
    mia_insert_str_2,
    mia_update_str_3,
)
from multiplex_code import _mia_get_parent_dir

from fzutils.cp_utils import _get_right_model_data
from fzutils.internet_utils import get_random_pc_ua
from fzutils.spider.fz_requests import Requests
from fzutils.common_utils import json_2_dict
from fzutils.time_utils import timestamp_to_regulartime
from fzutils.spider.crawler import Crawler

class MiaPintuanParse(MiaParse, Crawler):
    def __init__(self):
        super(MiaPintuanParse, self).__init__()
        self._set_headers()

    def _set_headers(self):
        self.headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            # 'Accept-Encoding:': 'gzip',
            'Accept-Language': 'zh-CN,zh;q=0.8',
            'Cache-Control': 'max-age=0',
            'Connection': 'keep-alive',
            'Host': 'm.mia.com',
            'Referer': 'https://m.mia.com/',
            'User-Agent': get_random_pc_ua(),  # 随机一个请求头
        }

    def get_goods_data(self, goods_id:str) -> dict:
        '''
        模拟构造得到data
        :param goods_id:
        :return: data dict类型
        '''
        if goods_id == '':
            self._data_error_init()
        else:
            data = {}
            # 常规商品手机地址
            goods_url = 'https://m.mia.com/item-' + str(goods_id) + '.html'
            # 常规商品pc地址
            # goods_url = 'https://www.mia.com/item-' + str(goods_id) + '.html'
            print('------>>>| 待抓取的地址为: ', goods_url)

            body = Requests.get_url_body(url=goods_url, headers=self.headers, had_referer=True, ip_pool_type=self.ip_pool_type)
            # print(body)

            if body == '':
                return self._data_error_init()

            is_mia_mian_page = Selector(text=body).css('div.item-center::text').extract_first()
            # print(is_mia_mian_page)
            if isinstance(is_mia_mian_page, str) and is_mia_mian_page == '进口母婴正品特卖':      # 单独处理拼团下架被定向到手机版主页的拼团商品
                print('++++++ 该拼团商品已下架，被定向到蜜芽主页, 此处将其逻辑删除!')
                tmp_pipeline = SqlServerMyPageInfoSaveItemPipeline()
                tmp_pipeline._update_table(sql_str=mia_update_str_2, params=(goods_id,))
                print('| +++ 该商品状态已被逻辑is_delete = 1 +++ |')
                gc.collect()
                return self._data_error_init()

            # 判断是否跳转，并得到跳转url, 跳转url的body, 以及is_hk(用于判断是否是全球购的商品)
            body, sign_direct_url, is_hk = self.get_jump_to_url_and_is_hk(body=body)

            try:
                # title, sub_title
                data['title'], data['sub_title'] = self.get_title_and_sub_title(body=body)

                # 获取所有示例图片
                all_img_url = self.get_all_img_url(goods_id=goods_id, is_hk=is_hk)
                if all_img_url == '':
                    return self._data_error_init()

                p_info = self._get_p_info(body=body)
                if p_info == []:
                    print('获取到的tmp_p_info为空值, 请检查!')
                    return self._data_error_init()
                data['p_info'] = p_info

                # 获取每个商品的div_desc
                div_desc = self.get_goods_div_desc(body=body)

                if div_desc == '':
                    print('获取到的div_desc为空值! 请检查')
                    return self._data_error_init()

                data['div_desc'] = div_desc

                '''
                获取每个规格的goods_id，跟规格名，以及img_url, 用于后面的处理
                '''
                sku_info = self.get_tmp_sku_info(body, goods_id, sign_direct_url, is_hk)
                if sku_info == {}:
                    return {}

                '''
                由于这个拿到的都是小图，分辨率相当低，所以采用获取每个goods_id的phone端地址来获取每个规格的高清规格图
                '''
                # # print(Selector(text=body).css('dd.color_list li').extract())
                # for item in Selector(text=body).css('dd.color_list li').extract():
                #     # print(item)
                #     try:
                #         # 该颜色的商品的goods_id
                #         color_goods_id = Selector(text=item).css('a::attr("href")').extract_first()
                #         # 该颜色的名字
                #         color_name = Selector(text=item).css('a::attr("title")').extract_first()
                #         # 该颜色的img_url
                #         color_goods_img_url = Selector(text=item).css('img::attr("src")').extract_first()
                #
                #         color_goods_id = re.compile('(\d+)').findall(color_goods_id)[0]
                #     except IndexError:      # 表示该li为这个tmp_url的地址 (单独处理goods_id)
                #         color_goods_id = goods_id
                #         color_name = Selector(text=item).css('a::attr("title")').extract_first()
                #         color_goods_img_url = Selector(text=item).css('img::attr("src")').extract_first()
                #     print(color_goods_id, ' ', color_name, ' ', color_goods_img_url)

                '''
                获取每个规格对应价格跟规格以及其库存
                '''
                if self.get_true_sku_info(sku_info=sku_info) == {}:     # 表示出错退出
                    return {}
                else:                                                   # 成功获取
                    true_sku_info, i_s, pintuan_time, all_sell_count = self.get_true_sku_info(sku_info=sku_info)
                    data['price_info_list'] = true_sku_info
                    data['pintuan_time'] = pintuan_time
                    data['all_sell_count'] = all_sell_count
                # pprint(true_sku_info)

                # 设置detail_name_list
                data['detail_name_list'] = self.get_detail_name_list(i_s=i_s, true_sku_info=true_sku_info)
                # print(detail_name_list)

                '''单独处理all_img_url为[]的情况'''
                if all_img_url == []:
                    all_img_url = [{'img_url': true_sku_info[0].get('img_url')}]

                data['all_img_url'] = all_img_url
                # pprint(all_img_url)

                '''
                单独处理得到goods_url
                '''
                if sign_direct_url != '':
                    goods_url = sign_direct_url

                data['goods_url'] = goods_url
                data['parent_dir'] = _mia_get_parent_dir(p_info=p_info)

            except Exception as e:
                print('遇到错误如下: ', e)
                return self._data_error_init()

            if data != {}:
                # pprint(data)
                self.result_data = data
                return data

            else:
                print('data为空!')
                return self._data_error_init()

    def deal_with_data(self) -> dict:
        '''
        处理得到规范的data数据
        :return: result 类型 dict
        '''
        data = self.result_data
        if data != {}:
            shop_name = ''
            account = ''
            title = data['title']
            sub_title = data['sub_title']

            # 商品价格和淘宝价
            try:
                tmp_price_list = sorted([round(float(item.get('pintuan_price', '')), 2) for item in data['price_info_list']])
                price = tmp_price_list[-1]  # 商品价格
                taobao_price = tmp_price_list[0]  # 淘宝价
            except IndexError:
                return self._data_error_init()

            detail_name_list = data['detail_name_list']
            price_info_list = data['price_info_list']
            all_img_url = data['all_img_url']
            p_info = data['p_info']
            div_desc = data['div_desc']
            parent_dir = data['parent_dir']
            is_delete = 0
            if price_info_list == [] or data['pintuan_time'] == {}:
                is_delete = 1

            result = {
                'goods_url': data['goods_url'],         # goods_url
                'shop_name': shop_name,                 # 店铺名称
                'account': account,                     # 掌柜
                'title': title,                         # 商品名称
                'sub_title': sub_title,                 # 子标题
                'price': price,                         # 商品价格
                'taobao_price': taobao_price,           # 淘宝价
                # 'goods_stock': goods_stock,            # 商品库存
                'detail_name_list': detail_name_list,   # 商品标签属性名称
                # 'detail_value_list': detail_value_list,# 商品标签属性对应的值
                'price_info_list': price_info_list,     # 要存储的每个标签对应规格的价格及其库存
                'all_img_url': all_img_url,             # 所有示例图片地址
                'p_info': p_info,                       # 详细信息标签名对应属性
                'div_desc': div_desc,                   # div_desc
                'pintuan_time': data['pintuan_time'],   # 拼团开始和结束时间
                'all_sell_count': data['all_sell_count'], # 总销量
                'is_delete': is_delete,                 # 用于判断商品是否已经下架
                'parent_dir': parent_dir,
            }
            # pprint(result)
            # print(result)
            # wait_to_send_data = {
            #     'reason': 'success',
            #     'data': result,
            #     'code': 1
            # }
            # json_data = json.dumps(wait_to_send_data, ensure_ascii=False)
            # print(json_data)
            return result

        else:
            print('待处理的data为空的dict, 该商品可能已经转移或者下架')
            return {}

    def insert_into_mia_pintuan_table(self, data, pipeline):
        try:
            tmp = _get_right_model_data(data=data, site_id=21)  # 采集来源地(蜜芽拼团商品)
        except:
            print('此处抓到的可能是蜜芽拼团券所以跳过')
            return None
        # print('------>>> | 待存储的数据信息为: |', tmp)
        print('------>>>| 待存储的数据信息为: |', tmp.get('goods_id'))

        params = self._get_db_insert_pintuan_params(item=tmp)
        _r = pipeline._insert_into_table(sql_str=mia_insert_str_2, params=params)

        return _r

    def update_mia_pintuan_table(self, data, pipeline):
        try:
            tmp = _get_right_model_data(data=data, site_id=21)
        except:
            print('此处抓到的可能是蜜芽拼团券所以跳过')
            return None
        # print('------>>> | 待存储的数据信息为: |', tmp)
        print('------>>>| 待存储的数据信息为: |', tmp.get('goods_id'))

        params = self._get_db_update_pintuan_params(item=tmp)
        pipeline._update_table(sql_str=mia_update_str_3, params=params)

    def _get_db_insert_pintuan_params(self, item) -> tuple:
        params = (
            item['goods_id'],
            item['goods_url'],
            item['create_time'],
            item['modify_time'],
            item['shop_name'],
            item['title'],
            item['sub_title'],
            item['price'],
            item['taobao_price'],
            dumps(item['detail_name_list'], ensure_ascii=False),  # 把list转换为json才能正常插入数据(并设置ensure_ascii=False)
            dumps(item['price_info_list'], ensure_ascii=False),
            dumps(item['all_img_url'], ensure_ascii=False),
            dumps(item['p_info'], ensure_ascii=False),  # 存入到PropertyInfo
            item['div_desc'],  # 存入到DetailInfo
            dumps(item['pintuan_time'], ensure_ascii=False),
            item['pintuan_begin_time'],
            item['pintuan_end_time'],
            item['all_sell_count'],
            item['pid'],
            item['site_id'],
            item['is_delete'],
            item['parent_dir'],
        )

        return params

    def _get_db_update_pintuan_params(self, item) -> tuple:
        params = (
            item['modify_time'],
            item['shop_name'],
            item['title'],
            item['sub_title'],
            item['price'],
            item['taobao_price'],
            dumps(item['detail_name_list'], ensure_ascii=False),
            dumps(item['price_info_list'], ensure_ascii=False),
            dumps(item['all_img_url'], ensure_ascii=False),
            dumps(item['p_info'], ensure_ascii=False),
            item['div_desc'],
            item['is_delete'],
            dumps(item['pintuan_time'], ensure_ascii=False),
            item['pintuan_begin_time'],
            item['pintuan_end_time'],
            item['all_sell_count'],
            item['parent_dir'],

            item['goods_id'],
        )

        return params

    def get_true_sku_info(self, sku_info):
        '''
        获取每个规格对应价格跟规格以及其库存
        :param sku_info:
        :return: {} 空字典表示出错 | (true_sku_info, i_s)
        '''
        goods_id_str = '-'.join([item.get('goods_id') for item in sku_info])
        # print(goods_id_str)
        tmp_url = 'https://p.mia.com/item/list/' + goods_id_str
        # print(tmp_url)

        tmp_body = Requests.get_url_body(url=tmp_url, headers=self.headers, had_referer=True, ip_pool_type=self.ip_pool_type)
        # print(tmp_body)

        tmp_data = json_2_dict(json_str=tmp_body).get('data', [])
        if tmp_data == []:
            return self._data_error_init()

        true_sku_info = []
        i_s = {}
        pintuan_time = {}  # 初始化
        all_sell_count = '0'
        for item_1 in sku_info:
            for item_2 in tmp_data:
                if item_1.get('goods_id') == str(item_2.get('id', '')):
                    i_s = item_2.get('i_s', {})
                    # print(i_s)
                    for item_3 in i_s.keys():
                        tmp = {}
                        if item_3 == 'SINGLE':
                            spec_value = item_1.get('color_name')
                        else:
                            spec_value = item_1.get('color_name') + '|' + item_3
                        normal_price = str(item_2.get('mp'))
                        detail_price = str(item_2.get('sp'))
                        try:
                            if item_2.get('g_l', []) == []:
                                break       # 表示如果该规格的拼团价为[], 则跳出这层循环

                            pintuan_price = str(item_2.get('g_l', [])[0].get('gp', ''))
                            # print(pintuan_price)
                        except:
                            print('获取该规格拼团价pintuan_price时出错!')
                            return self._data_error_init()

                        try:
                            s = str(item_2.get('g_l', [])[0].get('s', ''))  # 拼团开始时间
                            e = str(item_2.get('g_l', [])[0].get('e', ''))  # 拼团结束时间
                            s = self.change_to_number_str_time(s)
                            e = self.change_to_number_str_time(e)
                            pintuan_time = {
                                'begin_time': timestamp_to_regulartime(int(time.mktime(time.strptime(s, '%m %d %Y %H:%M:%S')))),
                                'end_time': timestamp_to_regulartime(int(time.mktime(time.strptime(e, '%m %d %Y %H:%M:%S')))),
                            }
                        except:
                            print('获取拼团pintuan_time时出错!')
                            return self._data_error_init()

                        try:
                            all_sell_count = str(item_2.get('g_l', [])[0].get('rsn', ''))
                        except:
                            print('获取拼团all_sell_count时出错!')
                            return self._data_error_init()

                        img_url = item_1.get('img_url')
                        rest_number = i_s.get(item_3)
                        if rest_number == 0:
                            pass
                        else:
                            tmp['spec_value'] = spec_value
                            tmp['pintuan_price'] = pintuan_price
                            tmp['detail_price'] = detail_price
                            tmp['normal_price'] = normal_price
                            tmp['img_url'] = img_url
                            tmp['rest_number'] = rest_number
                            true_sku_info.append(tmp)

        return (true_sku_info, i_s, pintuan_time, all_sell_count)

    def change_to_number_str_time(self, str):
        '''
        替换里面的月份的英文缩写为对应的数字月份
        :return:
        '''
        a = {
            'January': '01',
            'February': '02',
            'March': '03',
            'April': '04',
            'May': '05',
            'June': '06',
            'July': '07',
            'August': '08',
            'September': '09',
            'October': '10',
            'November': '11',
            'December': '12',
        }

        month = str.split(' ')[0]

        month = [a[key] for key in a if month == key][0]

        new_str = str.split(' ')
        new_str[0] = month

        return  ' '.join(new_str)

    def __del__(self):
        gc.collect()

if __name__ == '__main__':
    mia_pintuan = MiaPintuanParse()
    while True:
        mia_url = input('请输入待爬取的蜜芽商品地址: ')
        mia_url.strip('\n').strip(';')
        goods_id = mia_pintuan.get_goods_id_from_url(mia_url)
        mia_pintuan.get_goods_data(goods_id=goods_id)
        data = mia_pintuan.deal_with_data()
        pprint(data)