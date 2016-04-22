class MyTest():
    def __init__(self, x):
        self.x = x


test_list = []
for i in range(10):
    temp = MyTest(i)
    test_list.append(temp)


print any(x.x == 7 for x in test_list)
print any(x.x == 11 for x in test_list)
