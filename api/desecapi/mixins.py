class SetterMixin:
    def __setattr__(self, attrname, val):
        setter_func = 'setter_' + attrname
        if attrname in self.__dict__ and callable(getattr(self, setter_func, None)):
            super().__setattr__(attrname, getattr(self, setter_func)(val))
        else:
            super().__setattr__(attrname, val)
