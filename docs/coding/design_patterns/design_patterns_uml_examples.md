# Design Patterns with UML Examples

## OOP Basics

### Abstraction

Abstraction is the process of hiding implementation details.

Examples:

* Interfaces
* Abstract classes
* Virtual functions

### Encapsulation

Encapsulation is the practice of bundling data and methods that operate on that data within a single unit, typically a
class. It provides data hiding and access control.

Examples:

* Data hiding
* Access modifiers
* Getters and Setters
* Private members

### Inheritance

Inheritance is the process of creating a new class that is derived from an existing class.

Examples:

* Single inheritance
* Multiple inheritance
* Hierarchy of inheritance

### Polymorphism

Polymorphism is the ability of a single entity to take on multiple forms.

Examples:

* Virtual functions
* Overriding
* Overloading
* Dynamic binding
* Static binding
* Run-time polymorphism
	* Dynamic cast
* Compile-time polymorphism
	* Static cast

## OOP Principles

* Encapsulate what varies.
* Favour composition over inheritance
* Program to an interface, not an implementation.
* Dependency Inversion Principle
	* Depend upon abstractions. Do not depend upon concrete classes.
	* High-level should NOT depend on low-level, BOTH should depend on abstractions.
* Identify the aspects of your application that vary and separate them from what stays the same.
* Strive for loosely coupled designs between objects that interact.
* Classes should be open for extension, but closed for modification.
* Designed to be flexible and extensible.
* Designed to be able to change independently of other objects.

## Design Patterns

This directory contains detailed UML diagrams and examples for various design patterns. Each pattern includes:

* Pattern definition and keywords
* Links to source code examples
* Correct UML diagrams
* Common mistakes (Bad UML examples)
* Exercise questions
* Interview tips

### Creational Patterns

* **[Singleton Pattern](dp_singleton_uml.md)** - Ensures a class has only one instance and provides a global point of
  access to it.
	* Source: [singleton.h](examples/singleton.h)

* **[Factory Method Pattern](dp_factory_method_uml.md)** - Defines an interface for creating an object, but lets
  subclasses decide which class to instantiate.
	* Source: [factory.h](examples/factory.h)

* **[Abstract Factory Pattern](dp_abstract_factory_uml.md)** - Provides an interface for creating families of related
  or dependent objects without specifying their concrete classes.
	* Source: [factory.h](examples/factory.h)

### Structural Patterns

* **[Adapter Pattern](dp_adapter_uml.md)** - Converts the interface of a class into another interface clients expect.
	* Source: [adapter.h](examples/adapter.h)

* **[Decorator Pattern](dp_decorator_uml.md)** - Attaches additional responsibilities to an object dynamically.
	* Source: [decorator.h](examples/decorator.h)

* **[Composite Pattern](dp_composite_uml.md)** - Composes objects into tree structures to represent part-whole
  hierarchies.
	* Source: [composite.h](examples/composite.h)

* **[Facade Pattern](dp_facade_uml.md)** - Provides a unified interface to a set of interfaces in a subsystem.
	* Source: [facade.h](examples/facade.h)

* **[Proxy Pattern](dp_proxy_uml.md)** - Provides a surrogate or placeholder for another object to control access to it.
	* Source: [proxy.h](examples/proxy.h)

### Behavioral Patterns

* **[Observer Pattern](dp_observer_uml.md)** - Defines a one-to-many dependency between objects so that when one object
  changes state, all its dependents are notified and updated automatically.
	* Source: [observer.h](examples/observer.h)

* **[Strategy Pattern](dp_strategy_uml.md)** - Defines a family of algorithms, encapsulates each one, and makes them
  interchangeable.
	* Source: [strategic_duck.h](examples/strategy.h)

* **[Command Pattern](dp_command_uml.md)** - Encapsulates a request as an object, thereby letting you parameterize
  clients with different requests.
	* Source: [command.h](examples/command.h)

* **[State Pattern](dp_state_uml.md)** - Allows an object to alter its behavior when its internal state changes.
	* Source: [state.h](examples/state.h)

* **[Template Method Pattern](dp_template_method_uml.md)** - Defines the skeleton of an algorithm in a method, deferring
  some steps to subclasses.
	* Source: [template_method.h](examples/template_method.h)

* **[Iterator Pattern](dp_iterator_uml.md)** - Provides a way to access elements of an aggregate object sequentially
  without exposing its underlying representation.
	* Source: [iterator.h](examples/iterator.h)

* **[Mediator Pattern](dp_mediator_uml.md)** - Defines an object that encapsulates how a set of objects interact,
  promoting loose coupling by keeping objects from referring to each other explicitly.

## General Tips for Interviews

* **Know the "Gang of Four" classification**: Creational, Structural, Behavioral
* **Understand when NOT to use a pattern** - over-engineering is common
* **Be ready to draw diagrams on whiteboards** - practice sketching UML
* **Connect patterns to real projects** you've worked on
* **Know common variants** (like double-checked locking for Singleton)
* **Understand pattern combinations** - patterns work together in practice

## Exercise Questions

### Creational Patterns

* **Singleton**: What thread safety issues might arise with the basic implementation?
* **Factory Method**: When would you choose Abstract Factory over Factory Method?

### Structural Patterns

* **Adapter**: What's the difference between class adapter and object adapter?
* **Decorator**: How does Decorator differ from inheritance for extending functionality?
* **Composite**: What are the trade-offs between type safety and transparency?
* **Facade**: What's the difference between Facade and Adapter patterns?
* **Proxy**: When would you use each type of proxy (virtual, remote, protection)?

### Behavioral Patterns

* **Observer**: How does the Push vs Pull model affect the Observer pattern implementation?
* **Strategy**: What's the key difference between Strategy and State patterns?
* **Command**: How does Command pattern support undo/redo functionality?
* **State**: Who should be responsible for state transitions - Context or ConcreteState?
* **Template Method**: What's the Hollywood Principle and how does it relate to Template Method?
* **Iterator**: How do you handle concurrent modification during iteration?

## Resources

* [Real World Examples](examples/real_world_examples.h)
* [Anti-patterns](examples/antipatterns.h)
* [Compound Patterns](examples/compound.h)
