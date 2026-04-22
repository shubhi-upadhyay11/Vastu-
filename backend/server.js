const express = require("express");
const multer = require("multer");
const cors = require("cors");
const fs = require("fs");

const app = express();
app.use(cors());
app.use(express.json());

// Multer setup
const storage = multer.diskStorage({
  destination: (req, file, cb) => cb(null, "uploads/"),
  filename: (req, file, cb) => cb(null, Date.now() + "-" + file.originalname),
});

const upload = multer({ storage });

// API
app.post("/generate", upload.single("image"), (req, res) => {
  const { roomType, belief, length, width, notes } = req.body;

  const newData = {
    roomType,
    belief,
    length,
    width,
    notes,
    image: req.file ? req.file.filename : null,
  };

  let data = [];
  if (fs.existsSync("data.json")) {
    data = JSON.parse(fs.readFileSync("data.json"));
  }

  data.push(newData);
  fs.writeFileSync("data.json", JSON.stringify(data, null, 2));

  res.json({
    title: `${roomType} Layout Suggestion`,
    summary: `Place furniture in ${
      belief === "Vastu" ? "South-West" : "South"
    } direction`,
    layoutHints: [
      "Keep entrance clean",
      "Use natural light",
      "Avoid clutter",
    ],
  });
});

app.listen(5000, () => console.log("Server running on port 5000"));