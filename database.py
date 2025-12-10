from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import os

DATABASE_URL = "sqlite:///./app.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    
    profile = relationship("Profile", back_populates="user", uselist=False)
    experiences = relationship("Experience", back_populates="user")
    educations = relationship("Education", back_populates="user")
    skills = relationship("Skill", back_populates="user")

class Profile(Base):
    __tablename__ = "profiles"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    full_name = Column(String)
    phone = Column(String)
    linkedin = Column(String)
    website = Column(String)
    bio = Column(Text)
    
    user = relationship("User", back_populates="profile")

class Experience(Base):
    __tablename__ = "experiences"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String)
    company = Column(String)
    start_date = Column(String)
    end_date = Column(String) # "Present" or date
    description = Column(Text)
    
    user = relationship("User", back_populates="experiences")

class Education(Base):
    __tablename__ = "educations"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    school = Column(String)
    degree = Column(String)
    year = Column(String)
    
    user = relationship("User", back_populates="educations")

class Skill(Base):
    __tablename__ = "skills"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String)
    
    user = relationship("User", back_populates="skills")

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
