# coding:utf-8

'''
@author = super_fazai
@File    : tmall_real-time_update.py
@Time    : 2017/11/6 16:45
@connect : superonesfazai@gmail.com
'''

import sys
sys.path.append('..')

try:
    from celery_tasks import _get_tm_one_goods_info_task
except:
    pass

from tmall_parse_2 import TmallParse
from my_pipeline import SqlServerMyPageInfoSaveItemPipeline

from gc import collect
from settings import IS_BACKGROUND_RUNNING, MY_SPIDER_LOGS_PATH
from settings import TMALL_REAL_TIMES_SLEEP_TIME

from sql_str_controller import tm_select_str_3
from multiplex_code import (
    _get_async_task_result,
    _get_new_db_conn,
    _get_sku_price_trans_record,
    _get_spec_trans_record,
    _get_stock_trans_record,
    _print_db_old_data,
    from_tmall_type_get_site_id,
    to_right_and_update_tm_data,)

from fzutils.cp_utils import _get_price_change_info
from fzutils.celery_utils import _get_celery_async_results
from fzutils.spider.async_always import *

class TMUpdater(AsyncCrawler):
    """tm 实时更新"""
    def __init__(self, *params, **kwargs):
        AsyncCrawler.__init__(
            self,
            *params,
            **kwargs,
            log_print=True,
            log_save_path=MY_SPIDER_LOGS_PATH + '/天猫/实时更新/')
        self.tmp_sql_server = None
        self.goods_index = 1
        # asyncio 0 | celery 1
        self.crawl_type = 0
        # 并发量, 控制在50个, 避免更新is_delete=1时大量丢包!!
        self.concurrency = 50

    async def _get_db_old_data(self) -> (list, None):
        '''
        获取db需求更新的数据
        :return:
        '''
        self.tmp_sql_server = SqlServerMyPageInfoSaveItemPipeline()
        result = None
        try:
            result = list(self.tmp_sql_server._select_table(sql_str=tm_select_str_3))
        except TypeError:
            self.lg.error('TypeError错误, 原因数据库连接失败...(可能维护中)')

        await _print_db_old_data(logger=self.lg, result=result)

        return result
    
    async def _get_tmp_item(self, site_id, goods_id):
        tmp_item = []
        if site_id == 3:  # 从数据库中取出时，先转换为对应的类型
            tmp_item.append(0)
        elif site_id == 4:
            tmp_item.append(1)
        elif site_id == 6:
            tmp_item.append(2)

        tmp_item.append(goods_id)
        
        return tmp_item

    async def _update_db(self):
        while True:
            self.lg = await self._get_new_logger(logger_name=get_uuid1())
            result = await self._get_db_old_data()
            if result is None:
                pass
            else:
                self.goods_index = 1
                tasks_params_list = TasksParamsListObj(tasks_params_list=result, step=self.concurrency)
                index = 1
                while True:
                    try:
                        slice_params_list = tasks_params_list.__next__()
                    except AssertionError:  # 全部提取完毕, 正常退出
                        break

                    one_res, index = await self._get_one_res(
                        slice_params_list=slice_params_list,
                        index=index)
                    await self._except_sleep(res=one_res)

                self.lg.info('全部数据更新完毕'.center(100, '#'))  # sleep(60*60)

            if get_shanghai_time().hour == 0:  # 0点以后不更新
                await async_sleep(60 * 60 * 5.5)
            else:
                await async_sleep(5.5)
            collect()

    async def _get_one_res(self, slice_params_list, index) -> tuple:
        """
        获取slice_params_list对应的one_res
        :param slice_params_list:
        :return: (list, int)
        """
        tasks = []
        if self.crawl_type == 0:
            # asyncio
            for item in slice_params_list:
                index += 1
                self.lg.info('创建 task goods_id: {}'.format(item[1]))
                tasks.append(self.loop.create_task(self._update_one_goods_info(
                    item=item,
                    index=index)))

            one_res = await _get_async_task_result(tasks=tasks, logger=self.lg)

        elif self.crawl_type == 1:
            # celery
            for item in slice_params_list:
                index += 1
                site_id = item[0]
                goods_id = item[1]
                self.lg.info('创建 task goods_id: {}'.format(goods_id))
                tmp_item = await self._get_tmp_item(site_id=site_id, goods_id=goods_id)
                try:
                    async_obj = await self._create_celery_obj(
                        goods_id=tmp_item,
                        index=index,)
                    tasks.append(async_obj)
                except:
                    continue
            one_res = await _get_celery_async_results(tasks=tasks)

            # 获取新new_slice_params_list
            new_slice_params_list = []
            for item in slice_params_list:
                goods_id = item[1]
                for i in one_res:
                    try:
                        goods_id2 = i[1]
                        index = i[2]
                        if goods_id == goods_id2:
                            new_slice_params_list.append({
                                'index': index,
                                'before_goods_data': i[3],
                                'end_goods_data': i[4],
                                'item': item,
                            })
                            break
                        else:
                            continue
                    except IndexError:
                        continue

            for k in new_slice_params_list:
                item = k['item']
                index = k['index']
                goods_id = item[1]
                self.lg.info('创建 task goods_id: {}, index: {}'.format(goods_id, index))
                tasks.append(self.loop.create_task(self._update_one_goods_info_by_celery(
                    item=item,
                    index=index,
                    before_goods_data=k['before_goods_data'],
                    end_goods_data=k['end_goods_data'],)))
            one_res = await _get_async_task_result(tasks=tasks, logger=self.lg)

        else:
            raise NotImplemented

        return (one_res, index)

    async def _create_celery_obj(self, **kwargs):
        """
        创建celery obj
        :param kwargs:
        :return:
        """
        goods_id = kwargs.get('goods_id', [])
        index = kwargs['index']

        async_obj = _get_tm_one_goods_info_task.apply_async(
            args=[
                goods_id,
                index,
            ],
            expires=5 * 60,
            retry=False,
        )

        return async_obj

    async def _update_one_goods_info_by_celery(self, item, index, before_goods_data, end_goods_data):
        """
        更新单个goods
        :param item:
        :param index:
        :param before_goods_data:
        :param end_goods_data:
        :return:
        """
        res = False
        goods_id = item[1]

        self.tmp_sql_server = await _get_new_db_conn(
            db_obj=self.tmp_sql_server,
            index=index,
            logger=self.lg,
            remainder=50)

        if self.tmp_sql_server.is_connect_success:
            self.lg.info('updating goods_id: {}, index: {} ...'.format(goods_id, index))
            # 避免下面解析data错误休眠
            before_goods_data_is_delete = before_goods_data.get('is_detele', 0)
            if end_goods_data != {}:
                data = await self._get_new_goods_data(
                    data=end_goods_data,
                    item=item,
                    goods_id=goods_id,)
                res = to_right_and_update_tm_data(
                    data=data,
                    pipeline=self.tmp_sql_server,
                    logger=self.lg)

            else:  # 表示返回的data值为空值
                if before_goods_data_is_delete == 1:
                    # 检索后下架状态的, res也设置为True
                    res = True
                else:
                    self.lg.info('goods_id: {}, 阻塞休眠7s中...'.format(goods_id))
                    await async_sleep(delay=7., loop=self.loop)
                    # 改为阻塞进程, 机器会挂
                    # sleep(7.)

        else:  # 表示返回的data值为空值
            self.lg.error('数据库连接失败，数据库可能关闭或者维护中')
            await async_sleep(delay=5, loop=self.loop)

        index += 1
        self.goods_index = index
        collect()
        await async_sleep(TMALL_REAL_TIMES_SLEEP_TIME)

        return [goods_id, res]

    async def _update_one_goods_info(self, item, index):
        '''
        更新单个goods
        :param item: 
        :param index: 
        :return: 
        '''
        res = False
        site_id = item[0]
        goods_id = item[1]

        tmall = TmallParse(logger=self.lg)
        self.tmp_sql_server = await _get_new_db_conn(db_obj=self.tmp_sql_server, index=index, logger=self.lg, remainder=50)
        if self.tmp_sql_server.is_connect_success:
            self.lg.info('------>>>| 正在更新的goods_id为({}) | --------->>>@ 索引值为({})'.format(goods_id, index))
            tmp_item = await self._get_tmp_item(site_id=site_id, goods_id=goods_id)
            # self.lg.info(str(tmp_item))

            # ** 阻塞方式运行
            oo = tmall.get_goods_data(goods_id=tmp_item)
            # ** 非阻塞方式运行
            # loop = get_event_loop()
            # oo = await loop.run_in_executor(None, tmall.get_goods_data, tmp_item)
            # try:
            #     loop.close()
            #     try:
            #         del loop
            #     except:
            #         pass
            # except:
            #     pass

            before_goods_data_is_delete = oo.get('is_detele', 0)  # 避免下面解析data错误休眠
            # 阻塞方式
            data = tmall.deal_with_data()
            if data != {}:
                data = await self._get_new_goods_data(
                    data=data,
                    item=item,
                    goods_id=goods_id,)
                res = to_right_and_update_tm_data(data=data, pipeline=self.tmp_sql_server, logger=self.lg)
                
            else:
                if before_goods_data_is_delete == 1:
                    # 检索后下架状态的, res也设置为True
                    res = True
                else:
                    self.lg.info('------>>>| 阻塞休眠7s中...')
                    await async_sleep(delay=7., loop=self.loop)
                    # 改为阻塞进程, 机器会挂
                    # sleep(7.)

        else:  # 表示返回的data值为空值
            self.lg.error('数据库连接失败，数据库可能关闭或者维护中')
            await async_sleep(delay=5, loop=self.loop)

        index += 1
        self.goods_index = index
        try:
            del tmall
        except:
            pass
        collect()
        await async_sleep(TMALL_REAL_TIMES_SLEEP_TIME)
        
        return [goods_id, res,]

    async def _get_new_goods_data(self, **kwargs) -> dict:
        """
        处理并得到新的待存储goods_data
        :param item:
        :return:
        """
        data = kwargs.get('data', {})
        goods_id = kwargs.get('goods_id', '')
        item = kwargs.get('item', [])
        assert item != [], 'item != []'

        data['goods_id'] = goods_id
        data['shelf_time'], data['delete_time'] = get_shelf_time_and_delete_time(
            tmp_data=data,
            is_delete=item[2],
            shelf_time=item[5],
            delete_time=item[6])
        site_id = from_tmall_type_get_site_id(type=data['type'])
        price_info_list = old_sku_info = json_2_dict(item[7], default_res=[])
        try:
            old_sku_info = format_price_info_list(price_info_list=price_info_list, site_id=site_id)
        except AttributeError:  # 处理已被格式化过的
            pass
        new_sku_info = format_price_info_list(data['price_info_list'], site_id=site_id)
        data['_is_price_change'], data['sku_info_trans_time'], price_change_info = _get_sku_price_trans_record(
            old_sku_info=old_sku_info,
            new_sku_info=new_sku_info,
            is_price_change=item[8] if item[8] is not None else 0,
            db_price_change_info=json_2_dict(item[10], default_res=[]),
            old_price_trans_time=item[13])
        data['_is_price_change'], data['_price_change_info'] = _get_price_change_info(
            old_price=item[3],
            old_taobao_price=item[4],
            new_price=data['price'],
            new_taobao_price=data['taobao_price'],
            is_price_change=data['_is_price_change'],
            price_change_info=price_change_info)
        if data['_is_price_change'] == 1:
            self.lg.info('价格变动!! [{}]'.format(goods_id))
            # pprint(data['_price_change_info'])

        # 监控纯规格变动
        data['is_spec_change'], data['spec_trans_time'] = _get_spec_trans_record(
            old_sku_info=old_sku_info,
            new_sku_info=new_sku_info,
            is_spec_change=item[9] if item[9] is not None else 0,
            old_spec_trans_time=item[14])
        if data['is_spec_change'] == 1:
            self.lg.info('规格属性变动!! [{}]'.format(goods_id))

        # 监控纯库存变动
        data['is_stock_change'], data['stock_trans_time'], data['stock_change_info'] = _get_stock_trans_record(
            old_sku_info=old_sku_info,
            new_sku_info=new_sku_info,
            is_stock_change=item[11] if item[11] is not None else 0,
            db_stock_change_info=json_2_dict(item[12], default_res=[]),
            old_stock_trans_time=item[15])
        if data['is_stock_change'] == 1:
            self.lg.info('规格的库存变动!! [{}]'.format(goods_id))
        # self.lg.info('is_stock_change: {}, stock_trans_time: {}, stock_change_info: {}'.format(data['is_stock_change'], data['stock_trans_time'], data['stock_change_info']))

        return data

    async def _except_sleep(self, res):
        '''
        异常休眠
        :param res:
        :return:
        '''
        count = 0
        all_count_fail_sleep_time = 100.
        sleep_time = 50.
        for item in res:
            try:
                if not item[1]:
                    count += 1
            except IndexError:
                pass
        self.lg.info('Fail count: {}个, 并发量: {}个'.format(count, self.concurrency))
        if count/self.concurrency >= .9:
            # 全失败的休眠方式
            self.lg.info('抓取异常!! 休眠{}s中...'.format(all_count_fail_sleep_time))
            await async_sleep(all_count_fail_sleep_time)

        else:
            if count >= int(self.concurrency/5):
                self.lg.info('抓取异常!! 休眠{}s中...'.format(sleep_time))
                await async_sleep(sleep_time)

        return None

    def __del__(self):
        try:
            del self.lg
        except:
            pass
        try:
            del self.loop
        except:
            pass
        collect()

def _fck_run():
    _ = TMUpdater()
    loop = get_event_loop()
    loop.run_until_complete(_._update_db())
    try:
        del loop
    except:
        pass

def main():
    '''
    这里的思想是将其转换为孤儿进程，然后在后台运行
    :return:
    '''
    print('========主函数开始========')
    daemon_init()
    print('--->>>| 孤儿进程成功被init回收成为单独进程!')
    _fck_run()

if __name__ == '__main__':
    if IS_BACKGROUND_RUNNING:
        main()
    else:
        _fck_run()
