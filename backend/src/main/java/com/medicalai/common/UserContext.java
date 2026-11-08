package com.medicalai.common;

/**
 * 当前登录用户上下文
 */
public class UserContext {

    private static final ThreadLocal<String> USERNAME = new ThreadLocal<>();

    public static void setUsername(String username) {
        USERNAME.set(username);
    }

    public static String getUsername() {
        return USERNAME.get();
    }

    public static void clear() {
        USERNAME.remove();
    }
}
