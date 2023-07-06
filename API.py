from fastapi import FastAPI, Response, Request
import json
from datetime import datetime
from validation import checkDuplicates, searchDict, mainKeys
from table_models import engine
import pandas as pd
import numpy as np
from main_data import mainData
from importAPI import approveImport, importData, read_sql
import struct
from sqlalchemy import text
from urllib.parse import parse_qs
from sqlalchemy import text
import bcrypt

app = FastAPI()

@app.get("/data")
def data(response: Response, type = None, id:int = None, by = None):
    response.headers['Access-Control-Allow-Origin'] = "*" ##change to specific origin later (own website)
    if (type != None and id != None):
        if type == 'authors':
            query = '''select * from authors where author_id = ''' + "'" +str(id) + "'"
            author = pd.read_sql(query,con=engine()).replace(np.nan,None).to_dict('records')[0]
            return author
        if type == 'texts':
            if by == "author":
                query = '''SET statement_timeout = 60000;select 
                                text_id
                                ,text_title as "titleLabel"
                                ,text_author
                                ,text_q
                                ,text_title || 
                                case
                                    when text_original_publication_year is null then ' ' 
                                    when text_original_publication_year <0 then ' (' || abs(text_original_publication_year) || ' BC' || ') '
                                    else ' (' || text_original_publication_year || ' AD' || ') '
                                end as "bookLabel"
                            from texts where author_id = ''' + "'" +str(id) + "'"
                texts = pd.read_sql(query, con=engine()).replace(np.nan, None).to_dict('records')
            else:
                query = '''select * from texts where text_id = ''' + "'" +str(id) + "'"#getTexts(''' + id + ')' ##All texts of author_id = id
                texts = pd.read_sql(query, con=engine()).replace(np.nan, None).to_dict('records')[0]#.to_json(orient="table")
            return texts
    else: results = mainData()
    return results

@app.get("/lists")
def extract_list(response:Response, language=None, country=None, query_type=None):
    response.headers['Access-Control-Allow-Origin'] = "*" ##change to specific origin later (own website)
    queries = {'num_books':"/Users/tarjeisandsnes/lectura_api/API_queries/texts_by_author.sql",
                'no_books':"/Users/tarjeisandsnes/lectura_api/API_queries/authors_without_text.sql"}
    query = read_sql(queries[query_type])
    if language=="All": language=""
    if country=="All": query = query.replace("a.author_nationality ilike '%[country]%' and ", "")
    language = language.replace("'","''")
    country = country.replace("'","''")
    query = query.replace("[country]", country).replace("[language]",language)
    results = pd.read_sql(text(query), con=engine())
    if query_type=="num_books": results = results.sort_values(by=["texts"],ascending=False)
    results = results.replace(np.nan, None).to_dict('records')
    return results


@app.post("/new")
async def add_new(info:Request, response:Response, type):
    response.headers["Access-Control-Allow-Origin"] = "*"
    req_info = await info.json()
    req_info = checkDuplicates([req_info], mainData()[type])
    if len(req_info) == 0: return ("This already exists on the database")
    else: 
        req_info = req_info[0]
        cols = req_info.keys()
        reqs = ["author_name", "text_title", "edition_title"]
        found = 0
        for req in reqs: 
            if req in cols: found+=1
        if found == 0: return "error"
        vals = []
        newCols = []
        for col in cols:
            val = req_info[col]
            if val == "": continue
            else: newCols.append(col)
            if isinstance(val, str):
                if val == "": val = None 
                if "'" in val:
                    val = val.replace("'", "''")
                vals.append("'" + val + "'")
            else: vals.append(str(val))
        query = 'insert into ' + type + ' (' + ", ".join(newCols) + ') VALUES (' + ", ".join(vals) + ")"
        print(query)
        conn = engine().connect()
        conn.execute(query)
        conn.close()

@app.post("/edit")
async def edit_data(info: Request, response: Response, type, id:int):
    response.headers["Access-Control-Allow-Origin"] = "*"
    req_info = await info.json()
    if type == "authors": idType = "author_id"
    elif type == "texts": idType = "text_id"
    else: idType = "edition_id"
    print(req_info)
    conn = engine().connect()
    for j in req_info.keys():
        if j == idType: continue
        if isinstance(req_info[j],int): setData = str(req_info[j])
        else: setData = "'" + (req_info[j]) + "'"
        updateString = 'UPDATE ' + type + " SET " + j + " = " + setData + " WHERE " + idType + " = " + str(id)
        #insertDataString = '''INSERT INTO edits (id, type, variable, value) VALUES (%s, %s, %s, %s)''',(id, idType, j, req_info[j])
        conn.execute('''INSERT INTO edits (id, type, variable, value) VALUES (%s, %s, %s, %s)''',(id, idType, j, req_info[j]))
        conn.execute(updateString)
    conn.close()
    return {
        "status" : "SUCCESS",
        "data" : req_info
    }


@app.post("/import")
async def import_data(info: Request, response: Response):
    response.headers['Access-Control-Allow-Origin'] = "*" ##change to specific origin later (own website)
    reqInfo = await info.json()
    data = importData(reqInfo)
    return {
        "status" : "SUCCESS",
        "data" : data
    }

@app.post("/import/approve")
async def importApproval(type, response: Response, info: Request):
    response.headers['Access-Control-Allow-Origin'] = "*" ##change to specific origin later (own website)
    approvedData = await info.json()
    approveImport(approvedData, type)
    return "Imports have been approved"

@app.get("/import_data")
def data(response: Response, type = None):
    response.headers['Access-Control-Allow-Origin'] = "*" ##change to specific origin later (own website)
    file_name = type+"_import.json"
    with open(file_name) as json_file: data = json.load(json_file)
    return data

@app.get("/search")
def search(info: Request,response: Response, query, searchtype = None):
    response.headers['Access-Control-Allow-Origin'] = "*" ##change to specific origin later (own website)
    params = info.query_params
    query = query.replace("'","''").strip()
    allQuery = read_sql("/Users/tarjeisandsnes/lectura_api/API_queries/search_all.sql")
    search_params = {"query": f"%{query}%"}
    if searchtype == None:
        queryList = query.split(' ')
        if len(queryList) == 1:
            results = pd.read_sql(allQuery,con=engine(),params=search_params).drop_duplicates().to_dict("records")
            return results
        else:
            results = False#texts = False; authors = False
            for subQuery in queryList:
                search_params["query"]=f"%{subQuery}%"
                if isinstance(results, pd.DataFrame):
                    newResults = pd.read_sql(allQuery,con=engine(),params=search_params)
                    results = pd.merge(results,newResults,how="inner")
                else: results = pd.read_sql(allQuery,con=engine(),params=search_params).drop_duplicates()
            results = results.to_dict('records'); #.head(5)
            return results
    else: ###Detailed search by type
        parsed = parse_qs(str(params))
        filters = json.loads(parsed.get('filters', [''])[0])
        def find_results(query):
            queryBase = '''
            SET statement_timeout = 60000;
            select 
                *
            from authors
            WHERE  
            '''
            variables = searchtype.replace("s","")+"_id"
            filterString = ""
            whereClause = "WHERE "
            for n in range(len(filters)): #varlist should be a body in API request and optional
                var = filters[n]
                variables += ","+ var["value"] + '''::varchar(255) "''' + var["label"] + '''" \n''' #Add every search variable
                if n == len(filters)-1: filterString+= var["value"] + "::varchar(255) ILIKE '%" + query + "%'"
                else: filterString += var["value"] + "::varchar(255) ILIKE '%" + query + "%'" + " OR \n"
            query = queryBase.replace("*", variables).replace("WHERE ","WHERE " + filterString).replace("authors",str(searchtype))
            print(query)
            results = pd.read_sql(text(query), con=engine()).drop_duplicates()#.to_dict('records')
            return results
        queryList = query.split(" ")
        if len(queryList) == 1: results = find_results(queryList[0]).to_dict('records')
        else:
            results = False
            for subQuery in queryList:
                if isinstance(results, pd.DataFrame):
                    newResults = find_results(subQuery)
                    results = pd.merge(results, newResults, how="inner").drop_duplicates()
                else: results = find_results(subQuery)
            results = results.to_dict('records')
        return results

@app.post("/create_user")
async def createUser(response:Response,info:Request):
    response.headers['Access-Control-Allow-Origin'] = "*"
    response.headers['Content-Type'] = 'application/json'
    reqInfo = await info.json()
    email = reqInfo["user_email"].lower()
    username = reqInfo["user_name"].lower()
    conn = engine().connect()
    query = f"SELECT * FROM users WHERE user_email = '{email}' or user_name = '{username}'"
    df = pd.read_sql_query(query, conn)
    if not df.empty: 
        response.body = json.dumps({"message": "Duplicate"}).encode("utf-8")
        response.status_code = 200
    else:
        hashedPassword = reqInfo["user_password"]
        conn.execute("INSERT INTO USERS (user_name, user_email, hashed_password) VALUES (%s, %s, %s)", (username, email, hashedPassword))
        response.body = json.dumps({"user_id": pd.read_sql(query, conn).to_dict("records")[0]["user_id"]}).encode("utf-8")#.user_id)#return pd.read_sql(query,conn).to_dict("records")[0].user_id
        response.status_code = 200
        conn.close()
    return response

@app.get("/login_user")
def login(response:Response, user):
    response.headers['Access-Control-Allow-Origin'] = "*"
    if "@" in user: login_col = "user_email"
    else: login_col = "user_name"
    conn = engine().connect()
    query = "SELECT user_id, user_name, user_email, hashed_password from USERS where %s = '%s'" % (login_col, user.lower())
    df = pd.read_sql_query(query, conn)
    if df.empty: return False
    else:
        df = df.to_dict('records')[0]
        return {"pw":df["hashed_password"].tobytes().decode('utf-8')
                ,"user_id":df["user_id"], "user_name":df["user_name"],"user_email":df["user_email"]}
    #return user

@app.post("/delete_user")
async def delete_user(response:Response, info:Request):
    response.headers['Access-Control-Allow-Origin'] = "*"
    response.headers['Content-Type'] = 'application/json'
    reqInfo = await info.json()
    query = "UPDATE USERS SET HASHED_PASSWORD = NULL, USER_EMAIL = NULL, USER_NAME = '(deleted)_%s' WHERE USER_ID = %s" % (reqInfo["user_name"], reqInfo["user_id"])
    conn = engine().connect()
    conn.execute(query)
    conn.close()

@app.post("/create_list")
async def createList(response:Response, info:Request):
    response.headers['Access-Control-Allow-Origin'] = "*"
    reqInfo = await info.json()
    print(reqInfo)
    user_id = reqInfo["user_id"]
    list_name = reqInfo["list_name"]
    list_descr = reqInfo["list_description"]
    list_type = reqInfo["list_type"]
    conn = engine().connect()
    checkIfExists = "SELECT list_id from USER_LISTS where list_name = '%s'" % (list_name)
    if pd.read_sql(checkIfExists, conn).empty:
        conn.execute("INSERT INTO USER_LISTS (user_id, list_name, list_description, list_type) VALUES (%s, %s, %s, %s)",(user_id, list_name, list_descr, list_type))
        list_id = pd.read_sql("SELECT list_id FROM USER_LISTS where list_name = '%s'" % (list_name), conn).to_dict("records")[0]["list_id"]
        response.body = json.dumps({"list_id":list_id}).encode("utf-8")
        response.status_code = 200
        conn.close()
        return response

@app.get("/get_user_list")
def get_user_list(response:Response, list_id:int):
    response.headers['Access-Control-Allow-Origin'] = "*"
    if list_id>0: query = "SELECT L.*,u.user_name FROM USER_LISTS L join USERS u on u.user_id=l.user_id WHERE LIST_ID = '%s'" % list_id
    else: query = "SELECT L.* FROM OFFICIAL_LISTS L WHERE LIST_ID = '%s'" % abs(list_id)
    lists = pd.read_sql(query, con=engine())
    if lists.empty: return False
    else: 
        list_info = lists.to_dict('records')[0]
        if list_info["list_type"] == "authors": detail_query = read_sql("/Users/tarjeisandsnes/lectura_api/API_queries/list_elements_authors.sql")
        elif list_info["list_type"] == "texts": detail_query = read_sql("/Users/tarjeisandsnes/lectura_api/API_queries/list_elements_texts.sql")
        list_elements = pd.read_sql(detail_query.replace("[@list_id]",str(list_id)), con=engine()).fillna('').to_dict('records')
        print(list_elements)
        data = {"list_info": list_info, "list_detail": list_elements}
        return data

@app.post("/update_user_list")
async def update_user_list(response:Response, info:Request): #Update every list_info component, remove removed elements, add new ones
    response.headers['Access-Control-Allow-Origin'] = "*"
    reqInfo = await info.json()
    list_info = reqInfo["list_info"]
    list_id = list_info["list_id"]
    additions = reqInfo["additions"]
    removals = reqInfo["removals"]
    order_changes = reqInfo["order_changes"]
    conn = engine().connect()
    if len(additions)>0:
        for element in additions: conn.execute("INSERT INTO USER_LISTS_ELEMENTS (list_id,value) VALUES (%s, %s)",(list_id, element["value"]))
    if len(removals)>0: 
        for element in removals: conn.execute("DELETE FROM USER_LISTS_ELEMENTS WHERE list_id = '%s' and value = '%s'" % (list_id, element["value"]))
    if len(order_changes)>0:
        for n in range(len(order_changes)): 
            conn.execute("UPDATE USER_LISTS_ELEMENTS SET ORDER_RANK = %s WHERE ELEMENT_ID = %s",(n, order_changes[n]["element_id"]))
    if not list_info is False and len(list_info.keys())>1:
        for element in list_info.keys():
            conn.execute("UPDATE USER_LISTS SET %s = '%s' WHERE LIST_ID = %s" % (element,list_info[element], list_id))
    conn.execute("UPDATE USER_LISTS SET LIST_MODIFIED_DATE WHERE LIST_ID = %s" %(list_id))
    conn.close()
    response.status_code = 200
    response.body = json.dumps(reqInfo).encode('utf-8')
    return response

@app.post("/user_list_interaction")
async def user_list_interaction(response:Response, info:Request):
    response.headers["Access-Control-Allow-Origin"] = "*"
    reqInfo = await info.json()
    interaction_type = reqInfo["type"]
    list_id = reqInfo["list_id"]
    user_id = reqInfo["user_id"]
    delete = reqInfo["delete"]
    if not delete: query = "INSERT INTO USER_LISTS_%sS (list_id, user_id) VALUES (%s, %s)" % (interaction_type, list_id, user_id)
    else: query = "DELETE FROM USER_LISTS_%ss WHERE list_id = '%s' AND user_id = '%s'" % (interaction_type, list_id, user_id)
    conn = engine().connect()
    conn.execute(query)
    conn.close()
    response.status_code = 200
    return response

@app.get("/get_list_interactions")
def get_all_list_interactions(response:Response, user_id:int):
    response.headers['Access-Control-Allow-Origin'] = "*"
    query = '''SELECT COALESCE(W.LIST_ID, L.LIST_ID, DL.LIST_ID) as list_id
                , CASE WHEN W.LIST_ID IS NULL THEN FALSE ELSE TRUE END AS watchlist
                ,CASE WHEN L.LIST_ID IS NULL THEN FALSE ELSE TRUE END AS like
                ,CASE WHEN DL.LIST_ID IS NULL THEN FALSE ELSE TRUE END AS dislike
                from USER_LISTS_WATCHLISTS W 
                FULL JOIN USER_LISTS_LIKES L ON L.USER_ID = W.USER_ID AND L.LIST_ID = W.LIST_ID
                FULL JOIN USER_LISTS_DISLIKES DL ON DL.USER_ID = W.USER_ID AND DL.LIST_ID = W.LIST_ID
            WHERE W.USER_ID = '%s' OR L.USER_ID = '%s' OR DL.USER_ID = '%s'
    ''' % (user_id, user_id, user_id)
    lists = pd.read_sql(query, con=engine())
    if lists.empty: return False
    else: return lists.to_dict('records')

@app.get("/get_all_lists")
def get_all_lists(response:Response,user_id:int = None):
    response.headers['Access-Control-Allow-Origin'] = "*"
    query = read_sql("/Users/tarjeisandsnes/lectura_api/API_queries/list_of_lists.sql")
    lists = pd.read_sql(query,con=engine())
    if user_id:
            interaction_query = '''SELECT DISTINCT COALESCE(W.LIST_ID, L.LIST_ID, DL.LIST_ID) as list_id
                , CASE WHEN W.LIST_ID IS NULL THEN FALSE ELSE TRUE END AS watchlist
                ,CASE WHEN L.LIST_ID IS NULL THEN FALSE ELSE TRUE END AS like
                ,CASE WHEN DL.LIST_ID IS NULL THEN FALSE ELSE TRUE END AS dislike
                from USER_LISTS_WATCHLISTS W 
                FULL JOIN USER_LISTS_LIKES L ON L.USER_ID = W.USER_ID AND L.LIST_ID = W.LIST_ID
                FULL JOIN USER_LISTS_DISLIKES DL ON DL.USER_ID = W.USER_ID AND DL.LIST_ID = W.LIST_ID
            WHERE W.USER_ID = '%s' OR L.USER_ID = '%s' OR DL.USER_ID = '%s'
            ''' % (user_id, user_id, user_id)
            list_interactions = pd.read_sql(interaction_query, con=engine())
            if list_interactions.empty: lists = lists
            else: lists = pd.merge(lists, list_interactions, how="left",on="list_id")
    lists = lists.replace(np.nan,None).to_dict('records')
    return lists

@app.post("/upload_comment")
async def upload_comment(response:Response, info:Request):
    response.headers["Access-Control-Allow-Origin"] = "*"
    reqInfo = await info.json()
    user_id = reqInfo["user_id"]
    comment = reqInfo["comment"]
    parent_comment_id = reqInfo["parent_comment_id"]
    if parent_comment_id is None: parent_comment_id = "null"
    comment_type = reqInfo["type"]
    comment_type_id = reqInfo["type_id"]
    query = '''INSERT INTO COMMENTS (user_id, comment_content, parent_comment_id, comment_type, comment_type_id) VALUES 
        (%s, '%s', %s, '%s', %s) ''' % (user_id, comment, parent_comment_id, comment_type, comment_type_id)
    conn = engine().connect()
    conn.execute(query)
    conn.close()
    response.status_code = 200
    response.body = json.dumps(reqInfo).encode('utf-8')
    return response

@app.get("/extract_comments")
def comments(response:Response, comment_type, comment_type_id):
    response.headers['Access-Control-Allow-Origin'] = "*"
    query = '''SELECT C.*, U.USER_NAME FROM COMMENTS C JOIN USERS U ON U.USER_ID = C.USER_ID 
                WHERE COMMENT_TYPE = '%s' AND COMMENT_TYPE_ID = %s''' % (comment_type, comment_type_id)
    comments = pd.read_sql(query, con=engine()).replace(np.nan,None).to_dict('records')
    def create_comment_tree(comments, parent_id=None):
        tree = []
        for comment in comments:
            if comment['parent_comment_id'] == parent_id:
                comment['replies'] = create_comment_tree(comments, comment['comment_id'])
                tree.append(comment)
        return tree
    comment_tree = create_comment_tree(comments)
    return comment_tree