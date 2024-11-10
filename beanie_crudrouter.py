from typing import Any, Callable, List, Type, cast, Coroutine, Optional, Union

from fastapi_crudrouter.core import CRUDGenerator, NOT_FOUND
from fastapi_crudrouter.core._types import DEPENDENCIES, PAGINATION, PYDANTIC_SCHEMA as SCHEMA

try:
    from beanie import Document as Model
except ImportError:
    Model = None  # type: ignore
    beanie_installed = False
else:
    beanie_installed = True

CALLABLE = Callable[..., Coroutine[Any, Any, Model]]
CALLABLE_LIST = Callable[..., Coroutine[Any, Any, List[Model]]]


class BeanieCRUDRouter(CRUDGenerator[SCHEMA]):
    def __init__(
            self,
            schema: Type[SCHEMA],
            db_model: Type[Model],
            create_schema: Optional[Type[SCHEMA]] = None,
            update_schema: Optional[Type[SCHEMA]] = None,
            prefix: Optional[str] = None,
            tags: Optional[List[str]] = None,
            paginate: Optional[int] = None,
            get_all_route: Union[bool, DEPENDENCIES] = True,
            get_one_route: Union[bool, DEPENDENCIES] = True,
            create_route: Union[bool, DEPENDENCIES] = True,
            update_route: Union[bool, DEPENDENCIES] = True,
            delete_one_route: Union[bool, DEPENDENCIES] = True,
            delete_all_route: Union[bool, DEPENDENCIES] = True,
            **kwargs: Any
    ) -> None:
        assert (
            beanie_installed
        ), "Beanie ODM must be installed to use the BeanieCRUDRouter."

        self.db_model = db_model
        self._pk: str = 'id'

        super().__init__(
            schema=schema,
            create_schema=create_schema,
            update_schema=update_schema,
            prefix=prefix or db_model.describe()["name"].replace("None.", ""),
            tags=tags,
            paginate=paginate,
            get_all_route=get_all_route,
            get_one_route=get_one_route,
            create_route=create_route,
            update_route=update_route,
            delete_one_route=delete_one_route,
            delete_all_route=delete_all_route,
            **kwargs
        )

    def _get_all(self, *args: Any, **kwargs: Any) -> CALLABLE_LIST:
        async def route(pagination: PAGINATION = self.pagination) -> List[Model]:
            skip, limit = pagination.get("skip"), pagination.get("limit")
            query = self.db_model.find_all().skip(cast(int, skip))
            if limit:
                query = query.limit(limit)
            return await query.to_list()

        return route

    def _get_one(self, *args: Any, **kwargs: Any) -> CALLABLE:
        async def route(item_id: int) -> Model:
            model = await self.db_model.get(item_id)

            if model:
                return model
            else:
                raise NOT_FOUND

        return route

    def _create(self, *args: Any, **kwargs: Any) -> CALLABLE:
        async def route(model: self.create_schema) -> Model:  # type: ignore
            db_model = self.db_model(**model.dict())
            await db_model.save()

            return db_model

        return route

    def _update(self, *args: Any, **kwargs: Any) -> CALLABLE:
        async def route(
                item_id: int, model: self.update_schema  # type: ignore
        ) -> Model:
            obj = await self.db_model.get(item_id)
            await obj.set(model.dict(exclude_unset=True))
            return obj

        return route

    def _delete_all(self, *args: Any, **kwargs: Any) -> CALLABLE_LIST:
        async def route() -> List[Model]:
            await self.db_model.delete_many({})
            return await self._get_all()(pagination={"skip": 0, "limit": None})

        return route

    def _delete_one(self, *args: Any, **kwargs: Any) -> CALLABLE:
        async def route(item_id: int) -> Model:
            model: Model = await self._get_one()(item_id)
            await self.db_model.filter(id=item_id).delete()

            return model

        return route
