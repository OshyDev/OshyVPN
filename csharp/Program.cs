using Microsoft.Data.Sqlite;
using System.Security.Cryptography;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddSingleton<TaskStore>();
builder.Services.AddHealthChecks();
var app = builder.Build();
app.Use(async (context, next) => {
    var key = Environment.GetEnvironmentVariable("API_KEY");
    var supplied = context.Request.Headers["X-API-Key"].ToString();
    if (!string.IsNullOrEmpty(key) && context.Request.Path != "/health" &&
        !CryptographicOperations.FixedTimeEquals(SHA256.HashData(System.Text.Encoding.UTF8.GetBytes(key)),
            SHA256.HashData(System.Text.Encoding.UTF8.GetBytes(supplied)))) {
        context.Response.StatusCode = 401;
        await context.Response.WriteAsJsonAsync(new { detail = "Ugyldig API-nøgle" });
        return;
    }
    context.Response.Headers["X-Content-Type-Options"] = "nosniff";
    await next();
});
app.MapHealthChecks("/health");
app.MapGet("/api/tasks", (TaskStore store, bool? completed, int? limit, int? offset) =>
    Results.Ok(store.List(completed, Math.Clamp(limit ?? 50, 1, 200), Math.Max(offset ?? 0, 0))));
app.MapGet("/api/tasks/{id}", (string id, TaskStore store) => store.Get(id) is { } task ? Results.Ok(task) : Results.NotFound());
app.MapPost("/api/tasks", (CreateTask input, TaskStore store) => {
    if (string.IsNullOrWhiteSpace(input.Title) || input.Title.Length > 100 || (input.Description?.Length ?? 0) > 500)
        return Results.BadRequest(new { detail = "Ugyldige opgavefelter" });
    var item = store.Create(input);
    return Results.Created($"/api/tasks/{item.Id}", item);
});
app.MapPatch("/api/tasks/{id}", (string id, UpdateTask input, TaskStore store) => {
    try { return store.Update(id, input) is { } task ? Results.Ok(task) : Results.NotFound(); }
    catch (ArgumentException ex) { return Results.BadRequest(new { detail = ex.Message }); }
});
app.MapDelete("/api/tasks/{id}", (string id, TaskStore store) => store.Delete(id) ? Results.NoContent() : Results.NotFound());
app.MapGet("/api/vpn/status", () => Results.Ok(new { provider = "wireguard", state = "not_configured" }));
app.Run();

record CreateTask(string Title, string? Description, bool Completed = false);
record UpdateTask(string? Title, string? Description, bool? Completed);
record TaskItem([property: System.Text.Json.Serialization.JsonPropertyName("id")] string Id,
    [property: System.Text.Json.Serialization.JsonPropertyName("title")] string Title,
    [property: System.Text.Json.Serialization.JsonPropertyName("description")] string? Description,
    [property: System.Text.Json.Serialization.JsonPropertyName("completed")] bool Completed,
    [property: System.Text.Json.Serialization.JsonPropertyName("created_at")] string CreatedAt,
    [property: System.Text.Json.Serialization.JsonPropertyName("updated_at")] string UpdatedAt);
sealed class TaskStore {
    readonly string connection = Environment.GetEnvironmentVariable("API_DATABASE") ?? "Data Source=service.db";
    public TaskStore() { using var db = Open(); using var cmd = db.CreateCommand(); cmd.CommandText = "CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,title TEXT NOT NULL,description TEXT,completed INTEGER NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)"; cmd.ExecuteNonQuery(); }
    SqliteConnection Open() { var db = new SqliteConnection(connection); db.Open(); return db; }
    TaskItem Read(SqliteDataReader r) => new(r.GetString(0),r.GetString(1),r.IsDBNull(2)?null:r.GetString(2),r.GetInt32(3)!=0,r.GetString(4),r.GetString(5));
    public List<TaskItem> List(bool? done,int limit,int offset) { using var db=Open(); using var c=db.CreateCommand(); c.CommandText="SELECT * FROM tasks WHERE ($done IS NULL OR completed=$done) ORDER BY created_at DESC LIMIT $limit OFFSET $offset"; c.Parameters.AddWithValue("$done",done is null?DBNull.Value:done.Value?1:0); c.Parameters.AddWithValue("$limit",limit); c.Parameters.AddWithValue("$offset",offset); using var r=c.ExecuteReader(); var rows=new List<TaskItem>(); while(r.Read()) rows.Add(Read(r)); return rows; }
    public TaskItem? Get(string id) { using var db=Open(); using var c=db.CreateCommand(); c.CommandText="SELECT * FROM tasks WHERE id=$id"; c.Parameters.AddWithValue("$id",id); using var r=c.ExecuteReader(); return r.Read()?Read(r):null; }
    public TaskItem Create(CreateTask x) { var id=Guid.NewGuid().ToString(); var now=DateTimeOffset.UtcNow.ToString("O"); using var db=Open(); using var c=db.CreateCommand(); c.CommandText="INSERT INTO tasks VALUES($id,$title,$description,$done,$now,$now)"; c.Parameters.AddWithValue("$id",id); c.Parameters.AddWithValue("$title",x.Title.Trim()); c.Parameters.AddWithValue("$description",(object?)x.Description??DBNull.Value); c.Parameters.AddWithValue("$done",x.Completed?1:0); c.Parameters.AddWithValue("$now",now); c.ExecuteNonQuery(); return new TaskItem(id,x.Title.Trim(),x.Description,x.Completed,now,now); }
    public TaskItem? Update(string id,UpdateTask x) { var old=Get(id); if(old is null)return null; var title=x.Title??old.Title; var desc=x.Description??old.Description; if(string.IsNullOrWhiteSpace(title)||title.Length>100||(desc?.Length??0)>500)throw new ArgumentException("Ugyldige opgavefelter"); using var db=Open(); using var c=db.CreateCommand(); c.CommandText="UPDATE tasks SET title=$t,description=$d,completed=$done,updated_at=$now WHERE id=$id"; c.Parameters.AddWithValue("$t",title.Trim()); c.Parameters.AddWithValue("$d",(object?)desc??DBNull.Value); c.Parameters.AddWithValue("$done",(x.Completed??old.Completed)?1:0); c.Parameters.AddWithValue("$now",DateTimeOffset.UtcNow.ToString("O")); c.Parameters.AddWithValue("$id",id); c.ExecuteNonQuery(); return Get(id); }
    public bool Delete(string id) { using var db=Open(); using var c=db.CreateCommand(); c.CommandText="DELETE FROM tasks WHERE id=$id"; c.Parameters.AddWithValue("$id",id); return c.ExecuteNonQuery()>0; }
}
