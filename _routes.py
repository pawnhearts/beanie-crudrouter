import json
import re
from typing import List, Tuple, Annotated

from beanie import PydanticObjectId
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Depends, Response
from starlette import status

from auth import has_permission, cookie, SessionData, verifier
from models import Service, Category, Type, Order, User, RoleEnum, TStatusEnum

# stuff for react admin [WIP]

crud_router = APIRouter(dependencies=[Depends(cookie)])

@crud_router.get("/order_stats")
async def get_order_stats(user: SessionData = Depends(verifier)):
    if not has_permission(cls, user.role, "retrieve"):
        raise HTTPException(status_code=403, detail="Access Denied")

    return {
        "accepted": await Order.find(
            {
                "service_id": re.compile("^t_"),
                "t_status": {
                    "$in": [TStatusEnum.created.value, TStatusEnum.accepted.value]
                },
            }
        ).count(),
        "rejected": await Order.find(
            {
                "service_id": re.compile("^t_"),
                "t_status": {
                    "$in": [TStatusEnum.rejected.value, TStatusEnum.refund.value]
                },
            }
        ).count(),
    }

for cls in (Service, Category, Type, Order, User):

    def mk_rotes(cls):
        def get_cls(cls):
            async def get_obj(
                obj_id: PydanticObjectId, user: SessionData = Depends(verifier)
            ) -> cls:
                obj = await cls.get(obj_id, fetch_links=False)
                if obj is None:
                    raise HTTPException(status_code=404, detail="obj not found")
                await obj.fetch_all_links()
                return obj


            Annotated[cls, get_obj]
            return get_obj

        # CRUD

        @crud_router.post(f"/{cls.Settings.name}", response_model=cls)
        async def create_obj(obj: cls, user: SessionData = Depends(verifier)):
            if not has_permission(cls, user.role, "create", obj):
                raise HTTPException(status_code=403, detail="Access Denied")

            await obj.save()
            return obj

        @crud_router.put(f"/{cls.Settings.name}/{{obj_id}}", response_model=cls)
        async def put_obj_by_id(
            data: dict,
            obj: cls = Depends(get_cls(cls)),
            user: SessionData = Depends(verifier),
        ):
            if not has_permission(cls, user.role, "update", obj):
                raise HTTPException(status_code=403, detail="Access Denied")
            # if user.role != RoleEnum.superadmin:
            #     if getattr(obj, 'role', None) in (RoleEnum.superadmin, RoleEnum.admin):
            #         raise HTTPException(status_code=403, detail="Access Denied")
            #     if data.get('role', None) in (RoleEnum.superadmin.value, RoleEnum.admin.value):
            #         raise HTTPException(status_code=403, detail="Access Denied")


            for k, c in [('category_id', Category), ('type_id', Type), ('service_link', Service),]:
                if k in data:
                    if data[k]:
                        data[k] = ObjectId(data[k])
                        # data[k] = await c.get(data[k])
                    else:
                        del data[k]
            if user.role == RoleEnum.worker:
                data = {'t_status': data['t_status']}

            await obj.set(data)

            return obj

        @crud_router.get(f"/{cls.Settings.name}/{{obj_id}}", response_model=cls | dict)
        async def get_obj_by_id(
            obj: cls = Depends(get_cls(cls)), user: SessionData = Depends(verifier)
        ):
            if not has_permission(cls, user.role, "retrieve", obj):
                raise HTTPException(status_code=403, detail="Access Denied")
            # await obj.fetch_all_links()
            # return obj
            d = obj.dict()
            # for k, v in d.items():
            #     if k.endswith("_id"):
            #         if isinstance(v, dict):
            #             d[k] = v['id']
            #         elif isinstance(v, Link):
            #             d[k] = v.ref.id
            print(d)
            return d


        @crud_router.delete(f"/{cls.Settings.name}/{{obj_id}}")
        async def del_obj_by_id(
            obj: cls = Depends(get_cls(cls)), user: SessionData = Depends(verifier)
        ):
            if not has_permission(cls, user.role, "delete", obj):
                raise HTTPException(status_code=403, detail="Access Denied")
            await obj.delete()
            return Response(status_code=status.HTTP_200_OK)

        # LISTS

        @crud_router.get(f"/{cls.Settings.name}", response_model=List[dict]|List[cls] | cls)
        async def get_all_objs(
            response: Response,
            sort: str | None = None,
            range: Tuple[int, int] | None = None,
            filter: str | None = None,
            user: SessionData = Depends(verifier),
        ):
            if not has_permission(cls, user.role, "list"):
                raise HTTPException(status_code=403, detail="Access Denied")
            try:
                filter = json.loads(filter)
            except:
                filter = {}

            if q := filter.pop("q", None):
                filter["$or"] = [
                    {f: re.compile(q, re.IGNORECASE)} for f in ["email", "login", "title", "key", "link"]
                ]
            else:

                if "ids" in filter:
                    filter["_id"] = {"$in": filter.pop("ids")}
                if "id" in filter:
                    id = filter.pop('id')
                    if isinstance(id, list) and len(id) == 1:
                        id = id[0]
                    if isinstance(id, dict):
                        id = id['id']

                    obj = await cls.get(ObjectId(id))
                    if not has_permission(cls, user.role, "retrieve", obj):
                        raise HTTPException(status_code=403, detail="Access Denied")
                    return obj
                for k, v in list(filter.items()):
                    if v is None:
                        del filter[k]

                    if "_id" in k or k == "id":
                        for t in [(Category, 'category_id'), (Type, 'type_id')]:
                            if cls == Category and k == 'category_id':
                                del filter[k]
                                k = 'id'
                    if k == 'collection':
                        del filter[k]
                        continue
                    if isinstance(v, list):
                        if "_id" in k or k == "id":
                            def f(id):
                                if isinstance(id, dict):
                                    id = id['id']
                                return id

                            v = list(map(f, filter(None, v)))
                            if k!='service_id':
                                v= list(map(ObjectId, v))


                        filter[k] = {"$in": v}
                    else:
                        def f(id):
                            if isinstance(id, dict):
                                id = id['id']
                            return id

                        if "_id" in k or k == "id":
                            filter[k] = ObjectId(f(v))
                        if k == 'collection':
                            del filter[k]

                if "user_id" in filter:
                    filter["user_id"] = int(filter["user_id"])

            if 'manual' in filter:
                if filter.pop('manual'):
                    filter['service_id'] = re.compile('^t_')
                # else:
                #     filter['service_id'] = re.compile('^[^t]_')

            if user.role == RoleEnum.worker:
                # filter['manual'] = True
                filter['service_id'] = re.compile('^t_')
                # total = await cls.find({'service_id': re.compile('^t_')}).count()

            print("..", filter)
            total = await cls.find_many(filter).count()
            qs = cls.find_many(filter, fetch_links=True)  # , fetch_lnks=True)
            # qs = cls.find_all()
            if range is None:
                range = (0, 50)
                # if filter:
                #     range = (0, total)
            start, end = range
            response.headers["X-Content-Range"] = (
                f"{cls.Settings.name} {start}-{end}/{total}"
            )

            response.headers["Content-Range"] = (
                f"{cls.Settings.name} {start}-{end}/{total}"
            )

            response.headers["Access-Control-Expose-Headers"] = "Content-Range"
            if sort:
                try:
                    sort = json.loads(sort)
                    if sort[0] == "id":
                        sort[0] = "_id"
                    qs = qs.sort(f'{"-" if sort[1] == 'DESC' else "+"}{sort[0]}')
                    print(sort)
                except:
                    pass
            def nofetch(lst):
                for obj in lst:
                    d = obj.dict()
                    for k, v in obj.dict().items():
                        if k.endswith("_id"):
                            pass
                            # d[k]=ObjectId(v.id)
                            # print(d)
                    yield d

            async def dofetch(lst):
                res = []
                async for obj in lst:
                    await obj.fetch_all_links()
                    obj = obj.dict()
                    if cls is Order:
                        service = await Service.find_one({'api': obj['service_id']})
                        obj['service_title'] = service and service.title

                    res.append(obj)
                return res

            return await dofetch(qs.skip(start).limit(end - start))

        # # AGGREGATIONS
        #
        # @crud_router.get("/{cls.Settings.name}/aggregate/by_tag_name", response_model=List[AggregationResponseItem])
        # async def filter_objs_by_tag_name():
        #     return await cls.aggregate(
        #         aggregation_query=[
        #             {"$unwind": "$tag_list"},
        #             {"$group": {"_id": "$tag_list.name", "total": {"$sum": 1}}}
        #         ],
        #         item_model=AggregationResponseItem
        #     ).to_list()
        #
        #
        # @crud_router.get("/{cls.Settings.name}/aggregate/by_tag_color", response_model=List[AggregationResponseItem])
        # async def filter_notes_by_tag_color():
        #     return await cls.aggregate(
        #         aggregation_query=[
        #             {"$unwind": "$tag_list"},
        #             {"$group": {"_id": "$tag_list.color", "total": {"$sum": 1}}}
        #         ],
        #         item_model=AggregationResponseItem
        #     ).to_list()

    mk_rotes(cls)
