use axum::{
    extract::{DefaultBodyLimit, Path, Query, State},
    http::StatusCode,
    response::IntoResponse,
    routing::{get, patch},
    Json, Router,
};
use chrono::Utc;
use serde::{Deserialize, Serialize};
use std::{
    collections::HashMap,
    sync::{Arc, RwLock},
};
use uuid::Uuid;

// Datastrukturer
#[derive(Debug, Serialize, Clone)]
struct Task {
    id: String,
    title: String,
    description: Option<String>,
    completed: bool,
    created_at: String,
}

#[derive(Debug, Deserialize)]
struct CreateTask {
    title: String,
    description: Option<String>,
    #[serde(default)]
    completed: bool,
}

#[derive(Debug, Deserialize)]
struct UpdateTask {
    title: Option<String>,
    description: Option<String>,
    completed: Option<bool>,
}

#[derive(Debug, Deserialize)]
struct TaskQuery {
    completed: Option<bool>,
}

// Tråd-sikker delt tilstand (In-memory DB)
type Db = Arc<RwLock<HashMap<String, Task>>>;

#[tokio::main]
async fn main() {
    let db: Db = Arc::new(RwLock::new(HashMap::new()));

    let app = Router::new()
        .route("/health", get(health_check))
        .route("/api/tasks", get(get_all_tasks).post(create_task))
        .route("/api/tasks/:id", get(get_task).patch(update_task).delete(delete_task))
        .layer(DefaultBodyLimit::max(16 * 1024))
        .with_state(db);

    let address = std::env::var("RUST_API_BIND").unwrap_or_else(|_| "0.0.0.0:3001".into());
    let listener = tokio::net::TcpListener::bind(&address).await.expect("cannot bind API listener");
    println!("Rust API kører på http://{address}");
    axum::serve(listener, app).await.unwrap();
}

async fn health_check() -> impl IntoResponse {
    Json(serde_json::json!({
        "status": "ok",
        "timestamp": Utc::now().to_rfc3339()
    }))
}

async fn get_all_tasks(
    State(db): State<Db>,
    Query(query): Query<TaskQuery>,
) -> impl IntoResponse {
    let tasks = db.read().unwrap_or_else(|poisoned| poisoned.into_inner());
    let result: Vec<Task> = tasks
        .values()
        .filter(|t| query.completed.map_or(true, |c| t.completed == c))
        .cloned()
        .collect();
    Json(result)
}

async fn get_task(
    State(db): State<Db>,
    Path(id): Path<String>,
) -> Result<Json<Task>, StatusCode> {
    let tasks = db.read().unwrap_or_else(|poisoned| poisoned.into_inner());
    tasks.get(&id).cloned().map(Json).ok_or(StatusCode::NOT_FOUND)
}

async fn create_task(
    State(db): State<Db>,
    Json(payload): Json<CreateTask>,
) -> Result<(StatusCode, Json<Task>), (StatusCode, String)> {
    if payload.title.trim().is_empty() || payload.title.chars().count() > 100
        || payload.description.as_ref().is_some_and(|value| value.chars().count() > 500) {
        return Err((StatusCode::BAD_REQUEST, "Ugyldig titel længde".to_string()));
    }

    let id = Uuid::new_v4().to_string();
    let task = Task {
        id: id.clone(),
        title: payload.title,
        description: payload.description,
        completed: payload.completed,
        created_at: Utc::now().to_rfc3339(),
    };

    db.write().unwrap_or_else(|poisoned| poisoned.into_inner()).insert(id, task.clone());
    Ok((StatusCode::CREATED, Json(task)))
}

async fn update_task(
    State(db): State<Db>,
    Path(id): Path<String>,
    Json(payload): Json<UpdateTask>,
) -> Result<Json<Task>, StatusCode> {
    let mut tasks = db.write().unwrap_or_else(|poisoned| poisoned.into_inner());
    let task = tasks.get_mut(&id).ok_or(StatusCode::NOT_FOUND)?;

    if let Some(title) = payload.title {
        if title.trim().is_empty() || title.chars().count() > 100 {
            return Err(StatusCode::BAD_REQUEST);
        }
        task.title = title;
    }
    if let Some(description) = payload.description {
        if description.chars().count() > 500 { return Err(StatusCode::BAD_REQUEST); }
        task.description = Some(description);
    }
    if let Some(completed) = payload.completed {
        task.completed = completed;
    }

    Ok(Json(task.clone()))
}

async fn delete_task(
    State(db): State<Db>,
    Path(id): Path<String>,
) -> StatusCode {
    if db.write().unwrap_or_else(|poisoned| poisoned.into_inner()).remove(&id).is_some() {
        StatusCode::NO_CONTENT
    } else {
        StatusCode::NOT_FOUND
    }
}
