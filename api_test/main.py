from fastapi import FastAPI, Response, Request, HTTPException
#from fastapi.exceptions import RequestValidationError
#from fastapi.responses import PlainTextResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
import datetime
import xmltodict
import copy
from uuid import UUID
#from xml.parsers.expat import ExpatError
from os import environ



# DB_USER = environ.get("DB_USER", "user")
# DB_PASSWORD = environ.get("DB_PASSWORD", "password")
# DB_HOST = environ.get("DB_HOST", "localhost")
# DB_NAME = "async-blogs"
# SQLALCHEMY_DATABASE_URL = (
#     f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:5432/{DB_NAME}"
# )


app = FastAPI()

"""
Общий формат ответа от WEB-сервиса

Тело ответа представляет собой XML документ в кодировке UTF-8.
<RSP>
  <GUID>0b9fccc5-dadb-4f4a-9be4-85728e8c60d7</GUID>
  <DATE>2019-06-07T08:17:06+03:00</DATE>
  <METHOD>RBANK_GET_ACC_CALC</METHOD>
  <CODE>1</CODE>
  <STATUS>Успешно</STATUS>
  <RESULT>
   ..........
  </RESULT>
</RSP>


Стандартные коды и статусы ответов:
Код	Статус	Комментарий
1	Успешно	
2	Обрабатывается	Запрос с данным GUID находится в процессе обработки
10	Неизвестная ошибка	Любая ошибка, для которой нет отдельного кода
11	Ошибка аутентификации	
12	Некорректный запрос	Некорректно сформированный запрос, либо передан некорректный набор параметров для заданного метода.
13	Неизвестный метод	При запросе, в теге <METHOD>,  передано несуществующее название метода.
14	Ошибка метода	В процессе работы вызванного API метода возникла какая-то своя внутренняя «бизнес» - ошибка.
"""

# @app.get("/")
# async def root():
#     return {"message": "Hello World"}
#
#
# @app.get("/hello/{name}")
# async def say_hello(name: str):
#     return {"message": f"Hello {name}"}


# Шаблон ответа
return_xml_template = '''
<RSP>
  <GUID></GUID>
  <DATE></DATE>
  <METHOD></METHOD>
  <CODE></CODE>
  <STATUS></STATUS>
</RSP>
'''
return_xml_dict = xmltodict.parse(return_xml_template)


def response_err(error_text=None, code=None, guid=None, date=None, method=None):
    response_xml_dict = copy.deepcopy(return_xml_dict)
    response_xml_dict['RSP']['CODE'] = code
    if not code:
        response_xml_dict['RSP']['CODE'] = 10
    if error_text:
        response_xml_dict['RSP']['ERROR_TEXT'] = error_text
    if guid:
        response_xml_dict['RSP']['GUID'] = guid
    if date:
        response_xml_dict['RSP']['DATE'] = date
    if method:
        response_xml_dict['RSP']['METHOD'] = method
    return_xml = xmltodict.unparse(response_xml_dict, pretty=True)
    return Response(content=return_xml, media_type="application/xml")


@app.exception_handler(StarletteHTTPException)  # В случае вызова других методов помимо POST мы вернем ответ в виде XML
async def http_exception_handler(request, exc):
    return response_err(f'Privet status_code:{exc.status_code} detail:{exc.detail}')

# @app.exception_handler(RequestValidationError)
# async def validation_exception_handler(request, exc):
#     return PlainTextResponse(str(exc), status_code=400)

@app.post("/")
async def submit(request: Request):
    content_type = request.headers['Content-Type']
    if content_type == 'application/xml':
        body = await request.body()
        try:
            # Распарсим входящий текст в dict, чтобы понять вообще xml ли нам дали
            xml_dict = xmltodict.parse(body)
            xml_format = xmltodict.unparse(xml_dict, pretty=True)

            # Распознаем все ли нужные теги присутствуют в запросе
            request_guid = xml_dict['REQ']['GUID']
            request_method = xml_dict['REQ']['METHOD']
            request_auth = xml_dict['REQ']['AUTH']

            # Посчитаем дату нашего ответа (требование к возвлатному XML)
            response_date_offset = datetime.datetime.now().strftime("%z")
            if not response_date_offset:
                response_date_offset = '+03:00'
            else:
                response_date_offset = "".join(list(response_date_offset).insert(3, ':'))
            response_date = datetime.datetime.now().strftime(f"%Y-%m-%dT%H:%M:%S{response_date_offset}")

            # Если в запросе методы, которые, мы не обрабатываем, мы пришлем ответ с ошибкой об этом
            if request_method not in {'RBANK_GET_PAY_SPLIT','RBANK_SET_PAY_LIST'}:
                return response_err(f'Unknown method: {request_method}', 13, request_guid, response_date, request_method)

            # Валидация GUID
            try:
                response_guid = UUID(request_guid, version=1)
            except:
                return response_err(f'GUID in wrong format: {request_guid}', 12, request_guid, response_date, request_method)

            if request_method == 'RBANK_GET_PAY_SPLIT':
                # Проверка структуры 1
                try:
                    request_params = xml_dict['REQ']['PARAMS']
                except:
                    return response_err(f'Empty PARAMS in METHOD RBANK_GET_PAY_SPLIT', 13, request_guid, response_date,
                                        request_method)
                # Проверка структуры 2
                try:
                    request_params_pay_items = request_params['PAYLIST']['PAY']
                    request_params_pay_items_len = len(request_params_pay_items)
                except:
                    return response_err(f'Empty PARAMS.PAY in METHOD RBANK_GET_PAY_SPLIT', 13, request_guid, response_date,
                                        request_method)
                # Проверка на количество элементов PAY
                if request_params_pay_items_len < 1:
                    return response_err(f'Empty PARAMS.PAY.items in METHOD RBANK_GET_PAY_SPLIT', 13, request_guid,
                                        response_date,
                                       request_method)

                # Проверка на состав элементов PAY
                if not sorted(list(request_params_pay_items[0].keys())) == sorted(['@id', '@sum', '@tra']):
                    return response_err(f'Empty PARAMS.PAY.items in METHOD RBANK_GET_PAY_SPLIT not in id,sum,tra', 13, request_guid,
                                        response_date,
                                        request_method)

                # Проверка на типы данных элементов PAY

                # Запишем запрос в посгре

                # Запросим данные из посгре

                # Посчитаем распределение

                # Запишем ответ в посгре

                # Подготовим ответ
                response_xml_dict = copy.deepcopy(return_xml_dict)
                response_xml_dict['RSP']['CODE'] = 1
                response_xml_dict['RSP']['GUID'] = str(response_guid)
                response_xml_dict['RSP']['DATE'] = response_date
                response_xml_dict['RSP']['METHOD'] = request_method


            elif request_method =='RBANK_SET_PAY_LIST':
                # За один запрос в метод передаётся не более 1000 идентификаторов платежей.

                """ Пример успешного ответа от сервиса:
                <RSP>
                  <GUID>0b9fccc5-dadb-4f4a-9be4-85728e8c60d7</GUID>
                  <DATE>2019-06-07T08:17:06+03:00</DATE>
                  <METHOD>RBANK_SET_PAY_LIST</METHOD>
                  <CODE>14</CODE>
                  <STATUS>Ошибка метода</STATUS>
                  <RESULT>
                    <PAYS>
                      <PAY id="1041156" bid="31017474"/>
                      <PAY id="1041157" bid="31017475"/>
                      <PAY id="1041158" bid="31017476"/>
                      <PAY id="1041160" bid="31017478" err="Оплата уже существует" />
                    </PAYS>
                  </RESULT>
                </RSP>
                """
                response_xml_dict = copy.deepcopy(return_xml_dict)
                response_xml_dict['RSP']['CODE'] = 1
                response_xml_dict['RSP']['GUID'] = str(response_guid)
                response_xml_dict['RSP']['DATE'] = response_date
                response_xml_dict['RSP']['METHOD'] = request_method



        except Exception as e:
            return response_err(str(e))

        return Response(content=xmltodict.unparse(response_xml_dict, pretty=True), media_type="application/xml")
    else:
        raise HTTPException(status_code=400, detail=f'Content type {content_type} not supported')
