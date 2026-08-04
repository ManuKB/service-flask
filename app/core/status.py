"""Numeric status-code constants under the same dotted names FastAPI's
`fastapi.status` module exposes - lets every router keep writing
`status.HTTP_404_NOT_FOUND` etc. unchanged, only the import source differs."""

HTTP_200_OK = 200
HTTP_201_CREATED = 201
HTTP_204_NO_CONTENT = 204
HTTP_400_BAD_REQUEST = 400
HTTP_401_UNAUTHORIZED = 401
HTTP_403_FORBIDDEN = 403
HTTP_404_NOT_FOUND = 404
HTTP_409_CONFLICT = 409
HTTP_422_UNPROCESSABLE_ENTITY = 422
