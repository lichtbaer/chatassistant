# AI Assistant Platform - Architecture Guide

## 🏗️ System Architecture Overview

The AI Assistant Platform follows a **modular, scalable architecture** designed for enterprise deployment. The system is built using modern technologies and best practices to ensure reliability, performance, and maintainability.

### Architecture Principles

1. **Separation of Concerns**: Clear separation between frontend, backend, and data layers
2. **Microservices Ready**: Modular design that can be decomposed into microservices
3. **Scalability First**: Horizontal scaling capabilities from the ground up
4. **Security by Design**: Security considerations integrated at every layer
5. **Performance Optimized**: Caching, connection pooling, and efficient data access patterns

## 📐 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Client Layer                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  Web Browser  │  Mobile App  │  Desktop App  │  API Clients  │  Admin UI   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Presentation Layer                               │
├─────────────────────────────────────────────────────────────────────────────┤
│  NiceGUI Frontend  │  REST API Gateway  │  WebSocket Gateway  │  Admin API  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                             Application Layer                               │
├─────────────────────────────────────────────────────────────────────────────┤
│  Auth Service  │  Chat Service  │  Assistant Service  │  Knowledge Service │
│  Tool Service  │  User Service  │  Notification Service│  Analytics Service│
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Domain Layer                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  User Domain  │  Assistant Domain  │  Conversation Domain  │  Tool Domain  │
│  Knowledge Domain │  Notification Domain │  Analytics Domain │  Audit Domain│
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Data Layer                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│  PostgreSQL  │  Redis Cache  │  Weaviate Vector DB  │  File Storage  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           External Services                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│  AI Providers  │  MCP Tools  │  Monitoring  │  Backup Services  │  CDN      │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 🔧 Component Architecture

### Frontend Layer (NiceGUI)

The frontend is built using **React 19.1.0** with TypeScript, providing a modern, responsive web interface with real-time capabilities and enterprise-grade UI components.

#### Frontend Structure
```
frontend-react/
├── src/
│   ├── pages/                    # Page components
│   │   ├── Chat.tsx             # Main chat interface (14KB)
│   │   ├── KnowledgeBase.tsx    # Knowledge base management (12KB)
│   │   ├── SystemStatus.tsx     # System monitoring (5.1KB)
│   │   ├── Login.tsx            # Authentication (4.8KB)
│   │   ├── Register.tsx         # User registration (3.5KB)
│   │   ├── Admin.tsx            # Admin dashboard (3.1KB)
│   │   ├── Assistants.tsx       # AI assistants (2.6KB)
│   │   ├── Tools.tsx            # Tool integration (2.1KB)
│   │   ├── McpTools.tsx         # MCP tools (2.1KB)
│   │   ├── Conversations.tsx    # Conversation management (2.0KB)
│   │   ├── Profile.tsx          # User profile (1.9KB)
│   │   ├── Settings.tsx         # Application settings (1.9KB)
│   │   └── Dashboard.tsx        # Main dashboard (625B)
│   ├── components/              # Reusable UI components
│   │   ├── Layout.tsx           # Main layout with sidebar
│   │   ├── Sidebar.tsx          # Navigation sidebar
│   │   ├── HeaderBar.tsx        # Top header bar
│   │   ├── LazyComponents.tsx   # Lazy-loaded components
│   │   ├── ProtectedRoute.tsx   # Route protection
│   │   ├── ErrorBoundary.tsx    # Error handling
│   │   └── PerformanceMonitor.tsx # Performance tracking
│   ├── store/                   # State management (Zustand)
│   │   ├── authStore.ts         # Authentication state
│   │   ├── themeStore.ts        # Theme management
│   │   ├── chatStore.ts         # Chat state
│   │   └── knowledgeStore.ts    # Knowledge base state
│   ├── services/                # API integration
│   │   ├── api.ts               # API client
│   │   ├── authService.ts       # Authentication service
│   │   ├── websocketService.ts  # WebSocket communication
│   │   ├── chatService.ts       # Chat management
│   │   ├── knowledgeService.ts  # Knowledge base service
│   │   └── userService.ts       # User management
│   ├── utils/                   # Utilities and helpers
│   │   ├── performance.ts       # Performance monitoring
│   │   ├── validators.ts        # Input validation
│   │   └── helpers.ts           # Helper functions
│   ├── i18n/                    # Internationalization
│   │   ├── en.json              # English translations
│   │   └── de.json              # German translations
│   └── styles/                  # Styling and themes
│       ├── index.css            # Global styles
│       └── App.css              # App-specific styles
├── public/                     # Static assets
├── cypress/                    # E2E tests
└── __tests__/                  # Unit tests
    ├── components/              # Component tests
    ├── pages/                   # Page tests
    └── services/                # Service tests
```

#### Frontend Features
- **Modern React**: TypeScript, React 19.1.0 with concurrent features
- **Build System**: Vite 7.0.4 for fast development and optimized builds
- **Enterprise UI**: Ant Design 5.26.6 components with responsive design
- **State Management**: Zustand 5.0.6 for lightweight state management
- **Routing**: React Router 7.7.0 with protected routes
- **Internationalization**: i18next 25.3.2 with EN/DE support
- **Performance**: Lazy loading, code splitting, performance monitoring
- **Testing**: Vitest 2.1.8 + Jest 30.0.4 for comprehensive testing
- **Accessibility**: WCAG 2.1 AA compliant interface
- **Theme System**: Light/dark themes with dynamic switching
- **Error Handling**: Error boundaries and robust error management

### Backend Layer (FastAPI)

The backend is built using **FastAPI**, a modern, high-performance web framework for building APIs with Python.

#### Backend Structure
```
backend/
├── api/                     # API endpoints
│   ├── v1/                  # API version 1
│   │   ├── auth.py          # Authentication endpoints
│   │   ├── assistants.py    # Assistant endpoints
│   │   ├── conversations.py # Conversation endpoints
│   │   ├── knowledge.py     # Knowledge base endpoints
│   │   ├── tools.py         # Tool endpoints
│   │   ├── users.py         # User management endpoints
│   │   └── websocket.py     # WebSocket endpoints
│   └── dependencies.py      # API dependencies
├── services/                # Business logic services
│   ├── ai_service.py        # AI provider integration
│   ├── assistant_service.py # Assistant management
│   ├── conversation_service.py # Chat management
│   ├── knowledge_service.py # Knowledge base processing
│   ├── tool_service.py      # Tool integration
│   ├── user_service.py      # User management
│   └── weaviate_service.py  # Vector database service
├── models/                  # Database models
│   ├── user.py              # User model
│   ├── assistant.py         # Assistant model
│   ├── conversation.py      # Conversation model
│   ├── message.py           # Message model
│   ├── knowledge.py         # Knowledge base model
│   └── tool.py              # Tool model
├── schemas/                 # Pydantic schemas
│   ├── user.py              # User schemas
│   ├── assistant.py         # Assistant schemas
│   ├── conversation.py      # Conversation schemas
│   └── knowledge.py         # Knowledge base schemas
├── tools/                   # MCP tool implementations
│   ├── base.py              # Base tool class
│   ├── api_tools.py         # API integration tools
│   ├── file_tools.py        # File processing tools
│   ├── search_tools.py      # Search tools
│   └── analysis_tools.py    # Analysis tools
├── core/                    # Core configuration
│   ├── config.py            # Application configuration
│   ├── database.py          # Database setup
│   ├── security.py          # Security utilities
│   └── redis_client.py      # Redis client
└── main.py                  # Application entry point
```

#### Backend Features
- **RESTful API**: Comprehensive REST API with OpenAPI documentation
- **WebSocket Support**: Real-time bidirectional communication
- **Async/Await**: High-performance asynchronous processing
- **Dependency Injection**: Clean dependency management
- **Validation**: Comprehensive input validation with Pydantic
- **Security**: JWT authentication and role-based access control

### Data Layer

The data layer consists of multiple specialized databases and storage systems optimized for different use cases.

#### Database Architecture
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │     Redis       │    │    Weaviate     │
│   Primary DB    │    │     Cache       │    │   Vector DB     │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ Users           │    │ Sessions        │    │ Embeddings      │
│ Assistants      │    │ Cache Data      │    │ Vector Search   │
│ Conversations   │    │ Real-time Data  │    │ Similarity      │
│ Messages        │    │ Pub/Sub         │    │ Clustering      │
│ Knowledge Base  │    │ Job Queue       │    │ Recommendations │
│ Tools           │    │ Rate Limiting   │    │ Semantic Search │
│ Audit Logs      │    │ Locking         │    │ Content Analysis│
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

#### PostgreSQL (Primary Database)
- **Purpose**: Primary relational database for structured data
- **Tables**: Users, Assistants, Conversations, Messages, Knowledge Base, Tools
- **Features**: ACID compliance, transactions, relationships, constraints
- **Optimization**: Connection pooling, query optimization, indexing

#### Redis (Cache & Real-time)
- **Purpose**: Caching, session management, and real-time features
- **Use Cases**: Session storage, API response caching, real-time data
- **Features**: In-memory storage, pub/sub messaging, job queues
- **Optimization**: Memory optimization, persistence, clustering

#### Weaviate (Vector Database)
- **Purpose**: Vector storage for semantic search and embeddings
- **Use Cases**: Document embeddings, similarity search, recommendations
- **Features**: Vector similarity search, clustering, content analysis
- **Optimization**: Vector indexing, similarity algorithms, batch operations

## 🔄 Data Flow Architecture

### Authentication Flow
```
1. User Login Request
   ↓
2. Validate Credentials (PostgreSQL)
   ↓
3. Generate JWT Token
   ↓
4. Store Session (Redis)
   ↓
5. Return Token to Client
   ↓
6. Subsequent Requests Include Token
   ↓
7. Validate Token and Check Permissions
```

### Chat Flow
```
1. User Sends Message
   ↓
2. WebSocket Message to Backend
   ↓
3. Store Message (PostgreSQL)
   ↓
4. Process with AI Service
   ↓
5. Generate Response
   ↓
6. Store Response (PostgreSQL)
   ↓
7. Send Response via WebSocket
   ↓
8. Update UI in Real-time
```

### Knowledge Base Flow
```
1. Document Upload
   ↓
2. File Validation and Storage
   ↓
3. Text Extraction
   ↓
4. Document Chunking
   ↓
5. Generate Embeddings
   ↓
6. Store in Weaviate
   ↓
7. Index for Search
   ↓
8. Update Metadata (PostgreSQL)
```

### Tool Execution Flow
```
1. User Requests Tool Execution
   ↓
2. Validate Tool Parameters
   ↓
3. Execute MCP Tool
   ↓
4. Process Tool Results
   ↓
5. Format Response
   ↓
6. Store Execution Log
   ↓
7. Return Results to User
```

## 🔐 Security Architecture

### Authentication & Authorization
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   JWT Token     │    │   Role-Based    │    │   Permission    │
│   Generation    │    │   Access Control │    │   Validation    │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ Token Creation  │    │ Admin Role      │    │ Resource Access │
│ Token Validation│    │ User Role       │    │ Action Permissions│
│ Token Refresh   │    │ Guest Role      │    │ Data Filtering  │
│ Token Revocation│    │ Custom Roles    │    │ Audit Logging   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Security Layers
1. **Transport Security**: TLS/SSL encryption
2. **Authentication**: JWT-based token authentication
3. **Authorization**: Role-based access control (RBAC)
4. **Input Validation**: Comprehensive input sanitization
5. **Data Protection**: Encryption at rest and in transit
6. **Audit Logging**: Complete audit trail

## 📊 Performance Architecture

### Caching Strategy
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Application   │    │     Redis       │    │   CDN Cache     │
│     Cache       │    │     Cache       │    │   (Static)      │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ API Responses   │    │ Session Data    │    │ Static Assets   │
│ User Data       │    │ Real-time Data  │    │ Images          │
│ Configuration   │    │ Job Queues      │    │ CSS/JS Files    │
│ Permissions     │    │ Rate Limiting   │    │ Documents       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Performance Optimizations
1. **Database Optimization**: Connection pooling, query optimization, indexing
2. **Caching**: Multi-layer caching strategy
3. **Async Processing**: Non-blocking operations
4. **Load Balancing**: Horizontal scaling support
5. **CDN Integration**: Static asset delivery optimization

## 🔄 Integration Architecture

### External Service Integration
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   AI Providers  │    │   MCP Tools     │    │   Monitoring    │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ OpenAI API      │    │ Custom Tools    │    │ Performance     │
│ Anthropic API   │    │ API Integrations│    │ Error Tracking  │
│ Google AI       │    │ File Processing │    │ User Analytics  │
│ Local Models    │    │ Search Tools    │    │ System Health   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### API Integration Patterns
1. **RESTful APIs**: Standard HTTP-based integration
2. **WebSocket**: Real-time bidirectional communication
3. **MCP Protocol**: Model Context Protocol for tool integration
4. **Event-Driven**: Asynchronous event processing
5. **Batch Processing**: Efficient bulk operations

## 🚀 Deployment Architecture

### Container Architecture
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │    Backend      │    │   Database      │
│   Container     │    │   Container     │    │   Containers    │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ NiceGUI App     │    │ FastAPI App     │    │ PostgreSQL      │
│ Static Assets   │    │ WebSocket       │    │ Redis           │
│ Theme System    │    │ API Gateway     │    │ Weaviate        │
│ Responsive UI   │    │ Service Layer   │    │ File Storage    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Deployment Options
1. **Docker Compose**: Simple single-server deployment
2. **Kubernetes**: Production-grade orchestration
3. **Cloud Native**: AWS, Azure, Google Cloud deployment
4. **Hybrid**: Combination of on-premises and cloud

## 📈 Scalability Architecture

### Horizontal Scaling
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Load Balancer │    │   Frontend      │    │   Backend       │
│   (Nginx)       │    │   Instances     │    │   Instances     │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ Request Routing │    │ NiceGUI App 1   │    │ FastAPI App 1   │
│ SSL Termination │    │ NiceGUI App 2   │    │ FastAPI App 2   │
│ Static Serving  │    │ NiceGUI App N   │    │ FastAPI App N   │
│ Health Checks   │    │ Shared State    │    │ Shared State    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Scaling Strategies
1. **Application Scaling**: Multiple application instances
2. **Database Scaling**: Read replicas and connection pooling
3. **Cache Scaling**: Redis clustering and replication
4. **Storage Scaling**: Distributed file storage
5. **CDN Scaling**: Global content delivery

## 🔍 Monitoring & Observability

### Monitoring Architecture
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Application   │    │   Infrastructure│    │   Business      │
│   Monitoring    │    │   Monitoring    │    │   Metrics       │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ Performance     │    │ System Health   │    │ User Activity   │
│ Error Tracking  │    │ Resource Usage  │    │ Feature Usage   │
│ API Metrics     │    │ Network Traffic │    │ Conversion      │
│ Response Times  │    │ Disk Usage      │    │ Retention       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Observability Features
1. **Logging**: Structured logging with correlation IDs
2. **Metrics**: Performance and business metrics collection
3. **Tracing**: Distributed tracing for request flows
4. **Alerting**: Proactive monitoring and alerting
5. **Dashboards**: Real-time monitoring dashboards

# ConvoSphere Design System: Light & Dark Mode

## Color Palettes

### Light Mode
- **Background:** White Smoke (#F7F9FB)
- **Primary:** Deep Indigo (#23224A)
- **Secondary:** Soft Azure (#5BC6E8)
- **Accent:** Accent Lime (#B6E74B)
- **Surface:** Warm Sand (#F5E9DD)
- **Text:** Slate Grey (#23224A, #7A869A for secondary text)

### Dark Mode
- **Background:** Deep Indigo (#23224A)
- **Secondary Background:** #1A1A33
- **Primary:** Soft Azure (#5BC6E8)
- **Accent:** Accent Lime (#B6E74B)
- **Surface:** #2D2D4D
- **Text:** White Smoke (#F7F9FB) for main text, Soft Azure or Slate Grey for secondary info
- **Shadow/Hover:** Soft Azure with reduced opacity

## Design Principles for Both Modes
- **Adjust color values, do not invert:**
  - Use harmonious equivalents instead of inversion (e.g., darken or omit Warm Sand in dark mode)
- **Consistent accent colors:**
  - Accent Lime remains in both modes, reduce saturation in dark mode if needed
- **Optimize contrast:**
  - Ensure sufficient contrast for light text on dark backgrounds (at least AA, ideally AAA per WCAG)
  - In light mode, ensure Soft Azure is not too pale on white
- **Surface and depth:**
  - In dark mode, layer surfaces (various dark greys) for hierarchy
- **Use transparency subtly:**
  - For overlays, hover states, or modals
- **Illustrations and icons:**
  - Adaptive, e.g., outline icons or SVGs that dynamically adjust colors

## Example Application: Chat Window

**Light:**
- Background: White Smoke
- Text: Deep Indigo
- User bubble: Soft Azure with Deep Indigo text
- AI bubble: Warm Sand with Deep Indigo text
- Accent (e.g., active button): Accent Lime

**Dark:**
- Background: Deep Indigo
- Text: White Smoke
- User bubble: Soft Azure (slightly darkened) with Deep Indigo or White Smoke text
- AI bubble: #2D2D4D with Soft Azure or White Smoke text
- Accent: Accent Lime (slightly reduced brightness)

## Technical Implementation
- Two color palettes in the design system (light/dark)
- Toggle function (theme switcher) sets CSS variables in the `<head>`
- Components use only CSS variables
- SVGs/icons adapt via `currentColor` or dynamically to the theme
- Contrast and readability are checked according to WCAG

---

*This architecture guide provides a comprehensive overview of the AI Assistant Platform's technical design. For implementation details, please refer to the specific component documentation.* 