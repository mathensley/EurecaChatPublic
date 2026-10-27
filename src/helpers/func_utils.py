import inspect

def get_func_info(skip_args=None):
    """
    Retorna o nome da função chamadora e seus parâmetros em formato string.
    """

    default_skip_args = {"params", "func_name", "args_values", "config"}
    if skip_args is None:
        skip_args = default_skip_args
    else:
        skip_args = default_skip_args | set(skip_args)

    frame = inspect.currentframe().f_back 
    func_name = frame.f_code.co_name
    args_values = inspect.getargvalues(frame).locals

    args_items = [(k, v) for k, v in args_values.items() if k != "config"]
    parametros_str = ", ".join(
        f"{k}={v!r}" for k, v in args_items if k not in skip_args
    )

    return func_name, parametros_str
