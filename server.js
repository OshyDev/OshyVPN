import express from 'express';
import cors from 'cors';
import { v4 as uuidv4 } from 'uuid';
import { z } from 'zod';

const app = express();
app.use(cors());
app.use(express.json());

// Valideringsskemaer med Zod
const createTaskSchema = z.object({
  title: z.string().min(1, "Titel er påkrævet").max(100),
  description: z.string().max(500).optional(),
  completed: z.boolean().default(false)
});

const updateTaskSchema = createTaskSchema.partial();

// In-memory database
const db = new Map();

// Middleware til fejlhåndtering af validering
const validate = (schema) => (req, res, next) => {
  const result = schema.safeParse(req.body);
  if (!result.success) {
    return res.status(400).json({ error: "Valideringsfejl", details: result.error.format() });
  }
  req.validatedData = result.data;
  next();
};

// Endpoints
app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

app.get('/api/tasks', (req, res) => {
  let tasks = Array.from(db.values());
  if (req.query.completed !== undefined) {
    const isCompleted = req.query.completed === 'true';
    tasks = tasks.filter(t => t.completed === isCompleted);
  }
  res.json(tasks);
});

app.get('/api/tasks/:id', (req, res) => {
  const task = db.get(req.params.id);
  if (!task) return res.status(404).json({ error: 'Opgave ikke fundet' });
  res.json(task);
});

app.post('/api/tasks', validate(createTaskSchema), (req, res) => {
  const id = uuidv4();
  const newTask = {
    id,
    ...req.validatedData,
    created_at: new Date().toISOString()
  };
  db.set(id, newTask);
  res.status(201).json(newTask);
});

app.patch('/api/tasks/:id', validate(updateTaskSchema), (req, res) => {
  const existingTask = db.get(req.params.id);
  if (!existingTask) return res.status(404).json({ error: 'Opgave ikke fundet' });

  const updatedTask = { ...existingTask, ...req.validatedData };
  db.set(req.params.id, updatedTask);
  res.json(updatedTask);
});

app.delete('/api/tasks/:id', (req, res) => {
  if (!db.has(req.params.id)) return res.status(404).json({ error: 'Opgave ikke fundet' });
  db.delete(req.params.id);
  res.status(204).send();
});

// Global fejlhåndtering
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).json({ error: 'Intern serverfejl' });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`Server kører på http://localhost:${PORT}`));
