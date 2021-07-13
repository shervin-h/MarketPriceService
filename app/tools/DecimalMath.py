class DecimalMath:
    ONE = 10**18
    @classmethod
    def mul(cls,target, d):
        return (target*d) // cls.ONE

    @classmethod
    def divFloor(cls, target, d):
        return (target*cls.ONE)//d

    @classmethod
    def divCeil(cls, target, d):
        tmp =  target*cls.ONE
        if((tmp//d)*d < tmp):
            return (tmp//d) +1
        else:
            return tmp//d

    @classmethod
    def sqrt(cls, x):
        z = x // 2 +1
        y = x
        while (z < y):
            y = z
            z = (x // z + z) // 2
        return y
