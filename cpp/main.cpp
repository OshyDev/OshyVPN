#include <httplib.h>
#include <sqlite3.h>
#include <cstdlib>
#include <iostream>
#include <string>

static std::string env(const char* key, const char* fallback) { const char* v=std::getenv(key); return v?v:fallback; }
static std::string json_escape(const std::string& value) {
  std::string out; out.reserve(value.size()+2);
  for(unsigned char c:value) { switch(c) { case '"': out+="\\\""; break; case '\\': out+="\\\\"; break; case '\n': out+="\\n"; break; case '\r': out+="\\r"; break; case '\t': out+="\\t"; break; default: if(c<0x20) out+=' '; else out+=static_cast<char>(c); } }
  return out;
}
static bool authorized(const httplib::Request& req) {
  const auto key=env("API_KEY", ""); return key.empty() || (req.has_header("X-API-Key") && req.get_header_value("X-API-Key")==key);
}
int main() {
  sqlite3* db=nullptr; const auto path=env("API_DATABASE", "service.db");
  if(sqlite3_open(path.c_str(),&db)!=SQLITE_OK) { std::cerr<<"Database open failed\n"; return 1; }
  char* error=nullptr;
  if(sqlite3_exec(db,"CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,title TEXT NOT NULL,description TEXT,completed INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)",nullptr,nullptr,&error)!=SQLITE_OK) { std::cerr<<error<<"\n"; sqlite3_free(error); sqlite3_close(db); return 1; }
  httplib::Server api;
  api.Get("/health",[&](const httplib::Request&,httplib::Response& res){ res.set_content("{\"status\":\"ok\"}","application/json"); });
  api.Get("/api/tasks",[&](const httplib::Request& req,httplib::Response& res){
    if(!authorized(req)){res.status=401;res.set_content("{\"detail\":\"Unauthorized\"}","application/json");return;}
    sqlite3_stmt* stmt=nullptr; sqlite3_prepare_v2(db,"SELECT id,title,description,completed,created_at,updated_at FROM tasks ORDER BY created_at DESC LIMIT 200",-1,&stmt,nullptr);
    std::string json="["; bool first=true; while(sqlite3_step(stmt)==SQLITE_ROW){ if(!first)json+=","; first=false;
      auto field=[&](int i){const auto* p=sqlite3_column_text(stmt,i); return p?std::string(reinterpret_cast<const char*>(p)):std::string();};
      json+="{\"id\":\""+json_escape(field(0))+"\",\"title\":\""+json_escape(field(1))+"\",\"description\":"+(sqlite3_column_type(stmt,2)==SQLITE_NULL?"null":"\""+json_escape(field(2))+"\"")+",\"completed\":"+(sqlite3_column_int(stmt,3)?"true":"false")+",\"created_at\":\""+json_escape(field(4))+"\",\"updated_at\":\""+json_escape(field(5))+"\"}";
    } sqlite3_finalize(stmt); json+="]"; res.set_content(json,"application/json");
  });
  api.Get("/api/vpn/status",[&](const httplib::Request& req,httplib::Response& res){ if(!authorized(req)){res.status=401;return;} res.set_content("{\"provider\":\"wireguard\",\"state\":\"not_configured\"}","application/json"); });
  const int port=std::stoi(env("PORT","3002")); std::cout<<"C++ API listening on "<<port<<"\n";
  const bool started=api.listen(env("HOST","0.0.0.0"),port); sqlite3_close(db); return started?0:1;
}
