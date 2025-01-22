from typing import Any, Callable, Tuple

from requests import PreparedRequest


def body_matcher(params: str) -> Callable[..., Any]:
    def match(request: PreparedRequest) -> Tuple[bool, str]:
        try:
            body = request.body.decode("utf-8")
        except AttributeError:
            body = request.body
        if params in body:
            return True, ""
        else:
            return False, f"request.body doesn't match {params}: {body}"

    return match
