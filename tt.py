import asyncio


class TT(object):
    def __init__(self):
        self.task_list = []

    async def async_func(self, i: int):
        await asyncio.sleep(i)  # 模拟异步操作
        print(f"函数{i}的结果")

    def submit_async_task(self, fn, *args, **kwargs):
        self.task_list.append((fn, args, kwargs))

    def gather_async_result(self):
        async def async_gather():
            return await asyncio.gather(*[fn(*args, **kwargs) for fn, args, kwargs in self.task_list])

        results = asyncio.run(async_gather())
        self.task_list.clear()
        return results

    def run(self):
        self.submit_async_task(self.async_func, i=1)
        self.submit_async_task(self.async_func, i=2)
        self.submit_async_task(self.async_func, i=3)

        self.gather_async_result()


TT().run()
