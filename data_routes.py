'''
    This scripts define various routes for handling data related to power consumption of different device
'''

# import necessary dependencies
from fastapi import APIRouter, status, Depends
from fastapi.responses import HTMLResponse
from fastapi_jwt_auth import AuthJWT
from schemas import PowerConsumptionSchema, ResponseSchema, ErrorResonseSchema, StatisticsResonseSchema
from database import Session, engine
from models import User
from fastapi.exceptions import HTTPException
from werkzeug.security import generate_password_hash, check_password_hash
from fastapi.encoders import jsonable_encoder
from models import category_classes, categories
import pandas as pd
import ast
import redis
from init_redis import savePlot, saveStatistics

# Create an APIRouter for data-related routes
data_router = APIRouter(
    prefix='/data',
    tags=['Data Related End Points']
)   

# Session and Redis Setup
session = Session(bind=engine)
redis_client = redis.Redis(host='localhost', port=6379, db=0)

# Route for Getting Statistics
@data_router.get("/statistics/{category_name}", response_model=StatisticsResonseSchema, responses={401: {"description": "Invalid Token", "model": ErrorResonseSchema}, 404: {"description": "Not Found", "model": ErrorResonseSchema}})
def get_statistics(category_name: str, Authorize: AuthJWT = Depends()):
    """
        ## Get Statistics of specific device category
        This is protected endpoint and requires the following
        - category : string
        - accessToken        
    """
    print('inside statistics route')
    try:
        # Check if the request is authorized with a valid JWT token
        Authorize.jwt_required()
    except Exception as e:
        # If authorization fails, raise an HTTP 401 Unauthorized exception
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Token")

    if category_name not in categories:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Category '{category_name}' not found")

    response_bstring = redis_client.get(f'{category_name}_statistics')
    response_string = response_bstring.decode('utf-8')
    response = ast.literal_eval(response_string)

    return jsonable_encoder(response)

# Route for Getting Plot
@data_router.get("/plot/{category_name}")
def get_plot(category_name: str, Authorize:AuthJWT=Depends()):
    """
        ## Get Plot of specific device category
        This is protected endpoint and requires the following
        - category : string
        - accessToken
    """

    try:
        # Check if the request is authorized with a valid JWT token
        Authorize.jwt_required()
    except Exception as e:
        # If authorization fails, raise an HTTP 401 Unauthorized exception
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Token")

    # check if category is valid device name
    if category_name not in categories:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Category '{category_name}' not found")

    # fetching plot's json string from redis
    response_bstring = redis_client.get(f'{category_name}_plot')
    response_string = response_bstring.decode('utf-8')
    response = {'graphJSON': response_string}
    return jsonable_encoder(response)


# Route for Adding Data
@data_router.post("/add", status_code=status.HTTP_201_CREATED, response_model=ResponseSchema, responses={201: {"description": "successfully added the data"}, 401: {"description": "Invalid Token", "model": ErrorResonseSchema}, 404: {"description": "Not Found", "model": ErrorResonseSchema}})
async def add_data(dataPoint: PowerConsumptionSchema, Authorize: AuthJWT = Depends()):

    """
        ## Add the power data to specific device
        This is protected endpoint and requires the following
        - dataPoint : PowerConsumptionSchema
        - accessToken
    """

    try:
        # Check if the request is authorized with a valid JWT token
        Authorize.jwt_required()
    except Exception as e:
        # If authorization fails, raise an HTTP 401 Unauthorized exception
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Token")

    # Check if the specified category exists in category_classes dictionary
    if dataPoint.category not in category_classes:
        # If the category is not found, raise an HTTP 404 Not Found exception
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Category '{dataPoint.category}' not found")

    # Create a new data entry in the database for the specified category
    category_data = category_classes[dataPoint.category](timestamp=dataPoint.timestamp, power=dataPoint.power, category=dataPoint.category)
    session.add(category_data)
    session.commit()

    # update the plot and statistics in redis
    savePlot(dataPoint.category)
    saveStatistics(dataPoint.category)

    # Prepare a response message
    response = {
        "message": "Data added successfully"
    }

    return jsonable_encoder(response)