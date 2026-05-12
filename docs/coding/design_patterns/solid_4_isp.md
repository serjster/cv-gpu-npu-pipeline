# Interface Segregation Principle (ISP)

"Many client-specific interfaces are better than one general-purpose interface."

## Example 1: Multi-Function Office Devices

### Correct UML:
```mermaid
classDiagram
    class IPrintable {
        <<interface>>
        +print(doc)
    }
    class IScannable {
        <<interface>>
        +scan()
    }
    class IFaxable {
        <<interface>>
        +fax(number)
    }
    class AllInOne {
        +print()
        +scan()
        +fax()
    }
    class BasicPrinter {
        +print()
    }
    IPrintable <|-- AllInOne
    IScannable <|-- AllInOne
    IFaxable <|-- AllInOne
    IPrintable <|-- BasicPrinter
```
**Real-world benefit**:
- Network admin configuring print-only devices doesn't see scan/fax options
- Budget printers implement only `IPrintable`, no dummy methods
- Enterprise scanners implement `IScannable` + `IPrintable`, not forced to implement fax
- Each device declares exactly what it can do

### Bad UML:
```mermaid
classDiagram
    class IMultiDevice {
        <<interface>>
        +print()
        +scan()
        +fax()
        +photocopy()
        +email()
    }
    class BudgetPrinter {
        +print()
        +scan()
        +fax()
        +photocopy()
        +email()
    }
    IMultiDevice <|-- BudgetPrinter
    note for BudgetPrinter "Only print() works\nscan() throws Exception\nfax() throws Exception\nphotocopy() throws Exception\nemail() throws Exception"
```
**Real problem**: Users try to scan from budget printer, app crashes. 60% of interface is "not supported". Testing becomes nightmare - which methods actually work?

## Example 2: Cloud Storage Service

### Correct UML:
```mermaid
classDiagram
    class IReadable {
        <<interface>>
        +read(path)
    }
    class IWritable {
        <<interface>>
        +write()
        +delete()
    }
    class IVersionable {
        <<interface>>
        +getVersion()
        +rollback()
    }
    class S3Storage {
        +read()
        +write()
        +delete()
    }
    class Dropbox {
        +read()
        +write()
        +delete()
    }
    class GitRepo {
        +read()
        +write()
        +rollback()
    }
    class CDNCache {
        +read()
    }
    IReadable <|-- S3Storage
    IWritable <|-- S3Storage
    IReadable <|-- Dropbox
    IWritable <|-- Dropbox
    IReadable <|-- GitRepo
    IWritable <|-- GitRepo
    IVersionable <|-- GitRepo
    IReadable <|-- CDNCache
    note for CDNCache "Read-only cache"
```
**Real-world benefit**:
- CDN cache implements only `IReadable` - can't accidentally delete production files
- Basic S3 bucket implements `IReadable` + `IWritable`
- Git-backed storage adds `IVersionable` for rollback capability
- Each storage type exposes only what it supports

## Example 3: Authentication System

### Correct UML:
```mermaid
classDiagram
    class IAuthenticator {
        <<interface>>
        +login()
        +logout()
    }
    class IAuthorizer {
        <<interface>>
        +hasRole()
        +hasPermit()
    }
    class ISessionMgr {
        <<interface>>
        +create()
        +destroy()
        +refresh()
    }
    class BasicAuth {
        +login()
        +logout()
    }
    class JWTAuth {
        +login()
        +logout()
        +hasRole()
    }
    class OAuthProvider {
        +login()
        +logout()
        +hasRole()
        +create()
        +refresh()
    }
    class APIKeyAuth {
        +hasPermit()
    }
    IAuthenticator <|-- BasicAuth
    IAuthenticator <|-- JWTAuth
    IAuthorizer <|-- JWTAuth
    IAuthenticator <|-- OAuthProvider
    IAuthorizer <|-- OAuthProvider
    ISessionMgr <|-- OAuthProvider
    IAuthorizer <|-- APIKeyAuth
```
**Real-world benefit**:
- Microservices with API keys only need `IAuthorizer`, not full login system
- Mobile app with JWT needs `IAuthenticator` + `ISessionMgr` for token refresh
- Admin panel needs all three interfaces
- Each auth provider implements only required capabilities

### Bad UML:
```mermaid
classDiagram
    class IAuthSystem {
        <<interface>>
        +login()
        +logout()
        +refresh()
        +hasRole()
        +hasPermit()
        +createSession()
        +get2FACode()
        +socialLogin()
    }
    class APIKeyAuth {
        +hasPermit()
        +login()
        +refresh()
        +get2FACode()
        +socialLogin()
    }
    IAuthSystem <|-- APIKeyAuth
    note for APIKeyAuth "Stateless service-to-service\nOnly hasPermit() is relevant\nlogin() N/A - API keys don't login\nrefresh() N/A - API keys don't expire\nget2FACode() N/A - Not for services\nsocialLogin() N/A - Not applicable"
```
**Real problem**: API key validation forced to implement 7 irrelevant methods. Interface suggests features that don't exist. Developers waste time figuring out which methods actually work.

## Key Takeaways

- **Small, Focused Interfaces**: Better than one large, general-purpose interface
- **Client-Specific**: Design interfaces based on client needs
- **No Fat Interfaces**: Clients shouldn't depend on methods they don't use
- **Role Interfaces**: Define interfaces by roles/capabilities

## When to Apply

✅ Use ISP when:
- Clients use only a subset of interface methods
- Different clients need different sets of operations
- Interface implementations throw `NotImplementedException`
- Changes to interface affect clients that don't use changed methods

❌ Don't over-apply:
- Don't create one interface per method (too granular)
- Consider cohesion - related methods belong together
- Balance between flexibility and complexity

## Benefits

- **Decoupling**: Clients depend only on what they need
- **Flexibility**: Easy to add new implementations
- **Testability**: Mock only relevant behavior
- **Maintainability**: Changes don't ripple unnecessarily
- **Clear Contracts**: Interface explicitly states capabilities

## Related Principles

- Complements **SRP**: Focused interfaces support single responsibility
- Enables **LSP**: Smaller interfaces easier to substitute
- Works with **DIP**: Depend on minimal abstractions
- Supports **OCP**: Easy to extend without modification
