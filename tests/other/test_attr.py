class MyClass:
    def __init__(self):
        self.existing_attribute = "I exist"

    def do(self, name: str, **kwargs):
        print("do %s %s" % (name, kwargs))

    def __getattr__(self, name):
        return lambda **kwargs: self.do(name, **kwargs)


# 创建类的实例
obj = MyClass()

obj.haha(a=1, b=2)
