from pydantic.fields import FieldInfo

from fastapi import FastAPI
from pydantic import BaseModel



class Image(BaseModel):
    url: str
    name: str


class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float | None = None
    tags: set[str] = set()
    image: Image | None = None

type_map = {
    str : 'TextField',
    bool: 'BooleanField',
    int:  'NumberField',
    float: 'NumberField',
    date: 'DateInput'
    enum: 'SelectField',


}

for k, v in Item.__pydantic_fields__.items():
    print(f'<{v.annotatation} source="{k}">')

