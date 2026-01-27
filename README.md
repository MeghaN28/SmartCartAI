# SmartCartAI

SmartCartAI is an intelligent inventory management system designed to optimize retail operations through AI-powered decision-making. The system integrates a React Native mobile app frontend, a Java backend for data processing, and Python-based data generation tools to simulate and manage inventory, sales, and consumption data.

## Features

- **AI-Powered Inventory Management**: Automated decision-making for stock levels, expiry tracking, and waste reduction
- **Real-time Dashboard**: Monitor inventory status, at-risk items, and agent actions
- **Mobile App Interface**: Cross-platform React Native app for easy access
- **Data Simulation**: Generate realistic inventory, sales, and consumption datasets
- **Modular Architecture**: Separate frontend, backend, and data components for scalability

## Project Structure

```
SmartCartAI/
├── README.md
├── Agents/                    # AI agents for decision-making
├── Dataset/                   # Data generation and CSV files
│   ├── createdataset.py       # Python script to generate sample data
│   ├── inventory_master_50_unique.csv
│   ├── sales_50.csv
│   └── consumption_50.csv
├── SmartCartAIBackend/        # Java backend application
│   ├── README.md
│   ├── lib/
│   └── src/
│       └── App.java
└── SmartCartAIFrontEnd/       # React Native/Expo frontend
    ├── app.json
    ├── package.json
    ├── app/
    │   ├── _layout.tsx
    │   ├── (tabs)/
    │   │   ├── _layout.tsx
    │   │   ├── index.tsx      # Dashboard
    │   │   └── explore.tsx
    │   ├── inventory.tsx      # Inventory overview
    │   ├── decisions.tsx
    │   ├── impact.tsx
    │   └── modal.tsx
    ├── components/
    │   ├── StatCard.tsx
    │   ├── InventoryItem.tsx
    │   └── ...
    └── ...
```

## Installation

### Prerequisites

- Node.js (for frontend)
- Java JDK (for backend)
- Python 3 (for data generation)
- Expo CLI (for React Native development)

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd SmartCartAIFrontEnd
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npx expo start
   ```

### Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd SmartCartAIBackend
   ```

2. Compile and run the Java application:
   ```bash
   javac -d bin src/App.java
   java -cp bin App
   ```

### Data Generation

1. Navigate to the dataset directory:
   ```bash
   cd Dataset
   ```

2. Run the Python script to generate sample data:
   ```bash
   python createdataset.py
   ```

## Usage

### Mobile App

- **Dashboard**: View key metrics including total inventory items, at-risk items, agent actions, and waste reduction estimates
- **Inventory**: Browse inventory items with stock levels, expiry information, and risk assessments
- **Decisions**: Review AI-generated recommendations for inventory management
- **Impact**: Analyze the impact of AI decisions on operations

### Data Analysis

The dataset includes:
- `inventory_master_50_unique.csv`: Product catalog with categories, stock levels, and vendor information
- `sales_50.csv`: Daily sales data for 50 products
- `consumption_50.csv`: Consumption tracking including routine use, spoilage, and samples

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Technologies Used

- **Frontend**: React Native, Expo, TypeScript
- **Backend**: Java
- **Data Processing**: Python, Pandas, NumPy
- **AI/ML**: (To be implemented in Agents folder)