from typing import List, Tuple

from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException, Depends, Response
from starlette import status

from auth import has_permission, cookie, SessionData, verifier


def get_crud_router(model_class):
    crud_router = APIRouter(dependencies=[Depends(cookie)])

    def get_obj_for_model_class(cls):
        async def get_obj(
                obj_id: PydanticObjectId, user: SessionData = Depends(verifier)
        ) -> cls:
            obj = await cls.get(obj_id, fetch_links=False)
            if obj is None:
                raise HTTPException(status_code=404, detail="obj not found")
            await obj.fetch_all_links()
            return obj

        # Annotated[cls, get_obj]
        return get_obj

    @crud_router.post(f"/{model_class.Settings.name}", response_model=model_class)
    async def create(
            obj: model_class,
            dependencies=[Depends(has_permission(model_class, "create"))],
    ):
        await obj.save()
        return obj

    @crud_router.patch(
        f"/{model_class.Settings.name}/{{obj_id}}", response_model=model_class
    )
    async def update(
            data: dict,
            obj: model_class = Depends(get_obj_for_model_class(model_class)),
            dependencies=[Depends(has_permission(model_class, "update"))],
    ):
        await obj.set(data)
        return obj

    @crud_router.get(
        f"/{model_class.Settings.name}/{{obj_id}}", response_model=model_class
    )
    async def retrieve(
            obj: model_class = Depends(get_obj_for_model_class(model_class)),
            dependencies=[Depends(has_permission(model_class, "retrieve"))],
    ):
        return obj

    @crud_router.delete(f"/{model_class.Settings.name}/{{obj_id}}")
    async def delete(
            obj: model_class = Depends(get_obj_for_model_class(model_class)),
            dependencies=[Depends(has_permission(model_class, "delete"))],
    ):
        await obj.delete()
        return Response(status_code=status.HTTP_200_OK)

    @crud_router.get(
        f"/{model_class.Settings.name}",
        response_model=List[model_class],
    )
    async def obj_list(
            response: Response,
            range: Tuple[int, int] | None = None,
            dependencies=[Depends(has_permission(model_class, "list"))],
    ):
        total = await model_class.find_all().count()
        qs = model_class.find_all()
        if range is None:
            range = (0, 50)
        start, end = range
        response.headers["X-Content-Range"] = (
            f"{model_class.Settings.name} {start}-{end}/{total}"
        )

        response.headers["Access-Control-Expose-Headers"] = "Content-Range"

        return await qs.skip(start).limit(end - start).to_list(None)

    return crud_router
