def get_name(subname, domain_name):
    return '.'.join(filter(None, [subname, domain_name])) + '.'


class SetterMixin:
    def __setattr__(self, attrname, val):
        setter_func = 'setter_' + attrname
        if attrname in self.__dict__ and callable(getattr(self, setter_func, None)):
            super().__setattr__(attrname, getattr(self, setter_func)(val))
        else:
            super().__setattr__(attrname, val)
